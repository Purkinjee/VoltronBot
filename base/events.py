from datetime import datetime, timezone, timedelta

EVT_CHATCOMMAND = 'CHATCOMMAND'
EVT_CHATMESSAGE = 'CHATMESSAGE'
EVT_TIMER = 'TIMER'
EVT_STREAM_STATUS = 'STREAM_STATUS'
EVT_FIRST_MESSAGE = 'FIRST_MESSAGE'


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
	def __init__(self, command, args, display_name, user_id, is_mod, is_broadcaster):
		self.command = command.lower().strip()
		self.args = args
		self.display_name = display_name
		self.user_id = user_id
		self.is_mod = is_mod
		self.is_broadcaster = is_broadcaster

class ChatMessageEvent(Event):
	type = EVT_CHATMESSAGE
	def __init__(self, message, display_name, user_id, is_mod, is_broadcaster):
		self.message = message.strip()
		self.display_name = display_name
		self.user_id = user_id
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
	def __init__(self, message, display_name, user_id, is_mod, is_broadcaster):
		self.message = message
		self.display_name = display_name
		self.user_id = user_id
		self.is_mod = is_mod
		self.is_broadcaster = is_broadcaster
