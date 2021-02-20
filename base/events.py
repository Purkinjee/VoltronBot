from datetime import datetime, timezone, timedelta
from lib.common import get_broadcaster

EVT_CHATCOMMAND = 'CHATCOMMAND'
EVT_CHATMESSAGE = 'CHATMESSAGE'
EVT_TIMER = 'TIMER'
EVT_STREAM_STATUS = 'STREAM_STATUS'
EVT_FIRST_MESSAGE = 'FIRST_MESSAGE'
EVT_SUBSCRIPTION = 'SUBSCRIPTION'
EVT_BITS = 'BITS'
EVT_POINT_REDEMPTION = 'POINT_REDEMPTION'
EVT_HOST = 'HOST'
EVT_RAID = 'RAID'

class Event:
	"""
	Base class for all events
	"""
	type = 'EVENT'

class ChatCommandEvent(Event):
	"""
	Chat command event. This event is used for any line in chat beginning with !
	"""
	type = EVT_CHATCOMMAND
	def __init__(
		self,
		command,
		message,
		display_name,
		user_id,
		is_vip,
		is_mod,
		is_broadcaster,
		bypass_permissions = False,
		**kwargs
	):
		if command is None:
			command = ''
		self.command = command.lower().strip()

		if message is not None:
			self.message = str(message).strip()
			self.args = self.message.split(' ')
		else:
			self.args = []
			self.message = ''

		self.display_name = display_name
		self.user_id = user_id
		self.is_vip = is_vip
		self.is_mod = is_mod
		self.is_broadcaster = is_broadcaster
		self.bypass_permissions = bypass_permissions
		if kwargs:
			self.kwargs = kwargs
		else:
			self.kwargs = {}

		for key in kwargs:
			setattr(self, key, kwargs[key])

class ChatMessageEvent(Event):
	type = EVT_CHATMESSAGE
	def __init__(self, message, display_name, user_id, is_vip, is_mod, is_broadcaster):
		if message is not None:
			self.message = str(message).strip()
			self.args = self.message.split(' ')
		else:
			self.message = ''
			self.args = []

		self.display_name = display_name
		self.user_id = user_id
		self.is_vip = is_vip
		self.is_mod = is_mod
		self.is_broadcaster = is_broadcaster

class TimerEvent(Event):
	type = EVT_TIMER

	def __init__(self):
		pass

class StreamStatusEvent(Event):
	type = EVT_STREAM_STATUS
	def __init__(self, stream_id=None, title=None, started_at=None, viewer_count=None):
		self.stream_id = stream_id
		self.title = title
		if started_at:
			self.started_at = datetime.strptime(started_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone(timedelta(0)))
		else:
			self.started_at = None
		self.viewer_count = viewer_count

	@property
	def live_time(self):
		if not self.is_live:
			return 0

		now = datetime.utcnow().replace(tzinfo=timezone(timedelta(0)))
		return (now - self.started_at).seconds


	@property
	def is_live(self):
		if self.stream_id:
			return True

		return False

class FirstMessageEvent(Event):
	type = EVT_FIRST_MESSAGE
	def __init__(self, message, display_name, user_id, is_vip, is_mod, is_broadcaster):
		self.message = message
		self.display_name = display_name
		self.user_id = user_id
		self.is_vip = is_vip
		self.is_mod = is_mod
		self.is_broadcaster = is_broadcaster

class SubscriptionEvent(Event):
	type = EVT_SUBSCRIPTION
	def __init__(self, context, user_id, user_name, display_name, recipient_id,
		recipient_user_name, recipient_display_name, sub_plan, sub_plan_name,
		message, cumulative_months, streak_months, is_gift, duration):

		self.context = context
		self.user_id = user_id
		self.user_name = user_name
		self.display_name = display_name

		self.recipient_id = recipient_id
		self.recipient_user_name = recipient_user_name
		self.recipient_display_name = recipient_display_name

		if sub_plan is None:
			sub_plan = ''
		self.sub_plan = sub_plan
		self.sub_plan_name = sub_plan_name

		self.message = message

		self.cumulative_months = cumulative_months
		self.streak_months = streak_months

		self.is_gift = is_gift
		self.duration = duration

	@property
	def is_anonymous(self):
		return self.context == 'anonsubgift'

	@property
	def sub_tier(self):
		return {
			'prime': 1,
			'1000': 1,
			'2000': 2,
			'3000': 3
		}.get(str(self.sub_plan).lower(), 'Unknown')

	@property
	def sub_tier_name(self):
		return {
			'prime': 'Prime',
			'1000': 'Tier 1',
			'2000': 'Tier 2',
			'3000': 'Tier 3'
		}.get(str(self.sub_plan).lower(), 'Unknown')

class BitsEvent(Event):
	type = EVT_BITS
	def __init__(self, user_id, user_name, display_name, bits_used, message,
		is_anonymous, total_bits_used):
		self.user_id = user_id
		self.user_name = user_name
		self.display_name = display_name

		self.bits_used = bits_used
		self.message = message
		self.is_anonymous = is_anonymous
		self.total_bits_used = total_bits_used

class ChannelPointRedemption(Event):
	type = EVT_POINT_REDEMPTION
	def __init__(self, user_id, user_name, display_name, reward_id, title,
		prompt, cost, user_input):

		self.user_id = user_id
		self.user_name = user_name
		self.display_name = display_name

		self.reward_id = reward_id
		self.title = title
		self.cost = cost

		self.prompt = prompt
		self.user_input = user_input

class HostEvent(Event):
	type = EVT_HOST
	def __init__(self, display_name):
		self.display_name = display_name
		self._user_id = None

	@property
	def user_id(self):
		if self._user_id is not None:
			return self._user_id

		broadcaster = get_broadcaster()
		user_info = broadcaster.twitch_api.get_user(self.display_name.lower())

		self._user_id = user_info['id']
		return self._user_id


class RaidEvent(Event):
	type = EVT_RAID
	def __init__(self, display_name, user_id, viewer_count):
		self.display_name = display_name
		self.viewer_count = viewer_count
		self.user_id = user_id
