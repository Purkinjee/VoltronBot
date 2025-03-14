import threading
import websockets
import json
import time
import asyncio
import requests

import config
from base.events import SubscriptionEvent, GiftSubscriptionEvent, BitsEvent, ChannelPointRedemption
from lib.common import get_broadcaster

class PubSubThread:
	eventsub_ws_uri = "wss://eventsub.wss.twitch.tv/ws"
	#eventsub_ws_uri = "ws://127.0.0.1:8080/ws"

	subscription_uri = "https://api.twitch.tv/helix/eventsub/subscriptions"
	#subscription_uri = "http://127.0.0.1:8080/eventsub/subscriptions"
	def __init__(self, buffer_queue, event_queue, broadcaster):
		## PRODUCTION ##
		######
		## SET CLIENT_ID AND FERNET_KEY HERE FOR PRODUCTION
		######
		self.__client_id = ''
		self.__fernet_key = ''

		if hasattr(config, 'CLIENT_ID'):
			self.__client_id = config.CLIENT_ID

		if hasattr(config, 'FERNET_KEY'):
			self.__fernet_key = config.FERNET_KEY

		self.event_queue = event_queue
		self.buffer_queue = buffer_queue
		self.broadcaster = broadcaster
		self.oauth_tokens = broadcaster.oauth_tokens

		self.bgloop = asyncio.new_event_loop()
		bg_thread = threading.Thread(target=self.bgloop.run_forever)
		bg_thread.daemon = True
		bg_thread.start()

		self.ws = None

	def start(self):
		init_done = asyncio.run_coroutine_threadsafe(self.init_run(), self.bgloop)

	async def init_run(self):
		self.run_task = self.bgloop.create_task(self.run())

	async def run(self):
		self.reconnecting = True
		self.reconnect_url = None

		while True:
			if self.reconnecting:
				status = await self.connect(self.reconnect_url)
				if status:
					self.reconnecting = False
					self.reconnect_url = None
				else:
					self.buffer_queue.put(('WARN', 'PubSub not responding. Attempting to reconnect.'))
					await asyncio.sleep(10)
					continue

			await self._handle_response()
			if self.reconnecting:
				continue

	async def _handle_response(self):
		res = False
		try:
			ws_data = await asyncio.wait_for(self.ws.recv(), timeout=30)
			res = json.loads(ws_data)
		except asyncio.TimeoutError:
			return

		if res:
			if res['metadata'].get('message_type', None) == "session_reconnect":
				self.buffer_queue.put(('WARN', 'EventSub RECONNECT received'))
				self.reconnect_url = res['payload'].get('session', {}).get('reconnect_url', None)
				self.reconnecting = True
				return
			if res['metadata']['message_type'] != "notification":
				return
			topic = res['payload']['subscription']['type']

			if topic == "channel.subscribe":
				try:
					self.handle_sub(res['payload']['event'])
				except Exception as e:
					print(e)
			elif topic == "channel.subscription.message":
				try:
					self.handle_resub(res['payload']['event'])
				except Exception as e:
					print(e)
			elif topic == "channel.subscription.gift":
				try:
					self.handle_gift_sub(res['payload']['event'])
				except Exception as e:
					print(e)
			elif topic == "channel.cheer":
				try:
					self.handle_bits(res['payload']['event'])
				except Exception as e:
					print(e)
			elif topic == 'channel.channel_points_custom_reward_redemption.add':
				try:
					self.handle_point_redemption(res['payload']['event'])
				except Exception as e:
					print(e)

	def handle_sub(self, data):
		## Disable this for now as it's throwing events before the subscriber
		## sends a sub message making it "public"
		return True
		
		context = "sub"
		if data.get('is_gift', False):
			context = 'subgift'

		event = SubscriptionEvent(
			context,
			data.get('user_id'),
			data.get('user_login'),
			data.get('user_name'),
			data['tier'],
			'',
			1,
			1,
			data.get('is_gift', False),
			1
		)

		self.event_queue.put(event)
	
	def handle_resub(self, data):
		event = SubscriptionEvent(
			'resub',
			data.get('user_id'),
			data.get('user_login'),
			data.get('user_name'),
			data['tier'],
			data['message']['text'],
			data.get('cumulative_months', 1),
			data.get('streak_months', 1),
			False,
			data.get('duration_months', 1)
		)
		self.event_queue.put(event)

	def handle_gift_sub(self, data):
		context = 'subgift'
		if data.get('is_anonymous', False):
			context = 'anonsubgift'
		event = GiftSubscriptionEvent(
			context,
			data.get('user_id'),
			data.get('user_login'),
			data.get('user_name'),
			data['tier'],
			data.get('total', 1),
			data.get('cumulative_total', 1),
			data.get('is_anonymous', False)
		)
		self.event_queue.put(event)

	def handle_bits(self, data):
		event = BitsEvent(
			data.get('user_id'),
			data.get('user_login'),
			data.get('user_name'),
			data['bits'],
			data.get('message'),
			data['is_anonymous'],
			data['bits']
		)
		self.event_queue.put(event)

	def handle_point_redemption(self, data):
		event = ChannelPointRedemption(
			data['user_id'],
			data['user_login'],
			data['user_name'],
			data['reward']['id'],
			data['reward']['title'],
			data['reward'].get('prompt'),
			data['reward']['cost'],
			data.get('user_input')
		)
		self.event_queue.put(event)

	async def connect(self, reconnect_url = None):
		url = self.eventsub_ws_uri
		if reconnect_url is not None:
			url = reconnect_url

		self.buffer_queue.put(('STATUS', f'Connecting to EventSub {url}'))

		ws = await websockets.connect(url)

		recv_data = await ws.recv()
		res = json.loads(recv_data)

		session_id = res.get('payload', {}).get('session', {}).get('id')
		self.buffer_queue.put(('DEBUG', f"EventSub Session ID: {session_id}"))

		if session_id:
			self.buffer_queue.put(('STATUS', 'Connected to EventSub!'))
			if reconnect_url is None:
				self.subscribe_to_events(session_id)
			if self.ws is not None:
				await self.ws.close()
			self.ws = ws
			return True
		else:
			self.buffer_queue.put(('ERR', "Error Connecting to EventSub"))
			return False
	
	def subscribe_to_events(self, session_id):
		events = {
			"bits": {
				"type": "channel.cheer",
				"version": "1",
				"condition": {"broadcaster_user_id": str(self.broadcaster.twitch_user_id)},
				"transport": {
					"method": "websocket",
					"session_id": str(session_id)
				}
			},
			"subscriptions": {
				"type": "channel.subscribe",
				"version": "1",
				"condition": {"broadcaster_user_id": str(self.broadcaster.twitch_user_id)},
				"transport": {
					"method": "websocket",
					"session_id": str(session_id)
				}
			},
			"resubscribe": {
				"type": "channel.subscription.message",
				"version": "1",
				"condition": {"broadcaster_user_id": str(self.broadcaster.twitch_user_id)},
				"transport": {
					"method": "websocket",
					"session_id": str(session_id)
				}
			},
			"gift-sub": {
				"type": "channel.subscription.gift",
				"version": "1",
				"condition": {"broadcaster_user_id": str(self.broadcaster.twitch_user_id)},
				"transport": {
					"method": "websocket",
					"session_id": str(session_id)
				}
			},
			"channel-points": {
				"type": "channel.channel_points_custom_reward_redemption.add",
				"version": "1",
				"condition": {"broadcaster_user_id": str(self.broadcaster.twitch_user_id)},
				"transport": {
					"method": "websocket",
					"session_id": str(session_id)
				}
			}
		}
		for event_type in events:
			self.buffer_queue.put(('DEBUG', f"Subscribing to {events[event_type]['type']} event"))
			try:
				req = requests.post(
					self.subscription_uri,
					headers = {
						'Client-Id': self.__client_id,
						'Authorization': 'Bearer {token}'.format(token=self.oauth_tokens.token(self.__fernet_key)),
						'Content-Type': "application/json"
					},
					data = json.dumps(events[event_type]),
				)

			except requests.exceptions.ConnectionError:
				self.buffer_queue.put(("ERR", f"Error subscribing to {events[event_type]['type']} event"))
				continue

			if req.status_code == 202:
				self.buffer_queue.put(("DEBUG", f"Successfully subscribed to {events[event_type]['type']} event"))


	def shutdown(self):
		self.bgloop.call_soon_threadsafe(self.run_task.cancel)
