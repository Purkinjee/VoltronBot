import threading
import websockets
import json
import time
import asyncio

import config
from base.events import SubscriptionEvent, BitsEvent, ChannelPointRedemption
from lib.common import get_broadcaster

class PubSubThread:
	def __init__(self, buffer_queue, event_queue, broadcaster):
		## PRODUCTION ##
		########
		## SET FERNET KEY HERE FOR PRODUCTION
		########
		self.__fernet_key = ''
		if hasattr(config, 'FERNET_KEY'):
			self.__fernet_key = config.FERNET_KEY

		self.event_queue = event_queue
		self.buffer_queue = buffer_queue
		self.broadcaster = broadcaster

		self.bgloop = asyncio.new_event_loop()
		bg_thread = threading.Thread(target=self.bgloop.run_forever)
		bg_thread.daemon = True
		bg_thread.start()

		self.last_ping = 0
		self.last_pong = 0

		self.event_names = {
			"whispers": f"whispers.{broadcaster.twitch_user_id}",
			"bits": f"channel-bits-events-v2.{broadcaster.twitch_user_id}",
			"subs": f"channel-subscribe-events-v1.{broadcaster.twitch_user_id}",
			"redemptions": f"channel-points-channel-v1.{broadcaster.twitch_user_id}"
		}

		self.ws = None

	def start(self):
		init_done = asyncio.run_coroutine_threadsafe(self.init_run(), self.bgloop)
		#init_done.result()

	async def init_run(self):
		self.run_task = self.bgloop.create_task(self.run())

	async def run(self):
		self.reconnecting = True

		while True:
			if self.reconnecting:
				status = await self.connect()
				if status:
					self.reconnecting = False
				else:
					self.buffer_queue.put(('WARN', 'PubSub not responding. Attempting to reconnect.'))
					await asyncio.sleep(10)
					continue

			#handler = asyncio.create_task(self._handle_response())
			#await handler
			await self._handle_response()
			if self.reconnecting:
				continue

			time_elapsed_pong = time.time() - self.last_pong
			time_elapsed_ping = time.time() - self.last_ping
			if time_elapsed_pong > 150 and time_elapsed_ping > 100:
				await self.ping()
			elif time_elapsed_pong > 150 and time_elapsed_ping > 10:
				self.buffer_queue.put(('WARN', 'PubSub not responding. Attempting to reconnect.'))
				self.reconnecting = True
				#self.reconnect()

	async def _handle_response(self):
		res = False
		try:
			ws_data = await asyncio.wait_for(self.ws.recv(), timeout=30)
			res = json.loads(ws_data)
		except asyncio.TimeoutError:
			return

		if res:
			if res['type'] == 'PONG':
				self.pong_recv()
				return

			if res['type'] == 'RECONNECT':
				self.reconnecting = True
				self.buffer_queue.put(('WARN', 'RECONNECT received'))
				return

			topic = res['data']['topic']
			if topic == self.event_names['whispers']:
				pass
			elif topic == self.event_names['subs']:
				try:
					self.handle_sub(res['data'])
				except Exception as e:
					print(e)
			elif topic == self.event_names['bits']:
				try:
					self.handle_bits(res['data'])
				except Exception as e:
					print(e)
			elif topic == self.event_names['redemptions']:
				try:
					self.handle_point_redemption(res['data'])
				except Exception as e:
					print(e)

	def handle_sub(self, data):
		message = None
		m = data.get('message', None)
		if m:
			message = json.loads(m)

		if not message:
			return

		recipient_id = None
		recipient_user_name = None
		recipient_display_name = None

		if message['is_gift']:
			recipient_id = message.get('recipient_id')
			recipient_user_name = message.get('recipient_user_name')
			recipient_display_name = message.get('recipient_display_name')

		sub_message = ''
		if 'sub_message' in message:
			sub_message = message['sub_message'].get('message', '')

		event = SubscriptionEvent(
			message['context'],
			message.get('user_id'),
			message.get('user_name'),
			message.get('display_name'),
			recipient_id,
			recipient_user_name,
			recipient_display_name,
			message['sub_plan'],
			message['sub_plan_name'],
			sub_message,
			message.get('cumulative_months'),
			message.get('streak_months'),
			message['is_gift'],
			message.get('multi_month_duration', 1)
		)

		self.event_queue.put(event)

	def handle_bits(self, data):
		message = None
		m = data.get('message', None)
		if m:
			m = json.loads(m)
			message = m['data']
		if not message:
			return

		display_name = None
		if not message['is_anonymous']:
			broadcaster = get_broadcaster()
			user_info = broadcaster.twitch_api.get_user(message['user_name'])
			if user_info:
				display_name = user_info['display_name']

		event = BitsEvent(
			message.get('user_id'),
			message.get('user_name'),
			display_name,
			message['bits_used'],
			message.get('chat_message', ''),
			message['is_anonymous'],
			message.get('total_bits_used', 0)
		)

		self.event_queue.put(event)

	def handle_point_redemption(self, data):
		message = None
		m = data.get('message', None)
		if m:
			m = json.loads(m)
			message = m['data']
		if not m:
			return

		event = ChannelPointRedemption(
			message['redemption']['user']['id'],
			message['redemption']['user']['login'],
			message['redemption']['user']['display_name'],
			message['redemption']['reward']['id'],
			message['redemption']['reward']['title'],
			message['redemption']['reward'].get('prompt'),
			message['redemption']['reward']['cost'],
			message['redemption'].get('user_input')
		)

		self.event_queue.put(event)

	async def connect(self):
		self.buffer_queue.put(('STATUS', 'Connecting to PubSub'))
		self.ws = await websockets.connect("wss://pubsub-edge.twitch.tv")

		request = {
			"type": "LISTEN",
			"nonce": "butt",
			"data": {
				"topics": [
					#self.event_names['whispers'],
					self.event_names['bits'],
					self.event_names['subs'],
					self.event_names['redemptions']
				],
				"auth_token": self.broadcaster.oauth_tokens.token(self.__fernet_key)
			}
		}
		await self.ws.send(json.dumps(request))
		recv_data = await self.ws.recv()
		res = json.loads(recv_data)

		if res['error'] == '':
			self.buffer_queue.put(('STATUS', 'Connected to PubSub!'))
			return True
		else:
			self.buffer_queue.put(('ERR', res['error']))
			return False

	async def ping(self):
		await self.ws.send(json.dumps({"type": "PING"}))
		self.last_ping = time.time()
		self.buffer_queue.put(('DEBUG', 'PubSub Ping send'))

	def pong_recv(self):
		self.buffer_queue.put(('DEBUG', 'PubSub Pong recv'))
		self.last_pong = time.time()

	def shutdown(self):
		self.bgloop.call_soon_threadsafe(self.run_task.cancel)
