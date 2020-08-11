EVT_CHATCOMMAND = 'CHATCOMMAND'

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
