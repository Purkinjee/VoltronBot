from lib.common import get_all_acccounts
from lib.twitch_oauth import User
from lib.TwitchAPIHelper import TwitchAPIHelper
from lib.common import get_broadcaster, get_module_data_directory
from lib.ChatMessageParser import ChatMessageParser

class ModuleAdminCommand:
	"""
	Class used for creating admin commands for modules.
	These are only accessible through the main UI

	Args:
		trigger (string): The trigger for the command used in the UI
		action (func): Function to call when the command is triggered
		usage (string): Example usage displayed in help
		description (string): Description of the function of the command displayed in help
	"""
	def __init__(self, trigger, action, usage='', description=''):
		self.trigger = trigger
		self.action = action
		self.usage = usage
		self.description = description

	def execute(self, input):
		self.action(input, self)

class ModuleBase:
	"""
	Base class for all modules. Every module needs to inherit from this class.
	Instances are created automatically from the event loop
	"""
	def __init__(self, event_loop, voltron):
		self.admin_commands = {}
		self.voltron = voltron
		self.event_loop = event_loop

		broadcaster = get_broadcaster()
		self.twitch_api = None
		if broadcaster:
			self.twitch_api = broadcaster.twitch_api

		self.setup()

		self.voltron.register_module(self)

	def setup(self):
		"""
		This function will be called when the module is initialized.
		It should be overridden by the module
		"""
		pass

	def shutdown(self):
		"""
		This function will be called when the module is shut down
		It should be overridden by the module
		"""
		pass

	## Helper function
	def save_module_data(self, data):
		self.voltron.save_module_data(self, data)

	def get_module_data(self):
		return self.voltron.get_module_data(self)

	def event_listen(self, event_type, callback, event_params=None):
		self.event_loop.register_event(event_type, callback, event_params)

	def send_chat_message(self, message, twitch_id=None, event=None):
		parser = ChatMessageParser(message, event)
		parsed = parser.parse()
		self.voltron.send_chat_message(parsed, twitch_id)

	def send_private_message(self, user_name, message, twitch_id=None, event=None):
		self.voltron.send_private_message(user_name, message, twitch_id)

	def get_prompt(self, prompt=None, callback=None):
		return self.voltron.ui.mod_prompt(prompt, callback)

	def terminate_prompt(self, ident):
		self.voltron.ui.terminate_mod_prompt(ident)

	def update_status_text(self, text=None):
		self.voltron.ui.update_status_text(text)

	def buffer_print(self, type, msg):
		self.voltron.buffer_queue.put((type, msg))

	def get_counter(self, counter_name):
		return self.voltron.get_counter(counter_name)

	def get_all_counters(self):
		return self.voltron.get_all_counters()

	def set_counter(self, counter_name, value):
		self.voltron.set_counter(counter_name, value)

	def register_admin_command(self, command):
		if command.trigger in self.admin_commands:
			raise Exception('Trigger {} already exists'.format(command.trigger))

		self.admin_commands[command.trigger] = command

	def available_admin_commands(self):
		return self.admin_commands.keys()

	def admin_command(self, trigger):
		return self.admin_commands.get(trigger, None)

	def play_audio(self, path, **kwargs):
		self.event_loop.media_queue.put(('audio', path, kwargs))

	def get_commands(self, twitch_id, is_mod=False, is_broadcaster=False):
		return []

	def select_account(self, callback):
		account_list = self.list_accounts()
		selected_user = None

		def selection_made(prompt):
			if prompt.lower().strip() == 'c':
				self.update_status_text()
				return True
			try:
				selection = int(prompt)
			except:
				return False

			if selection < 0 or selection > len(account_list):
				self.buffer_print('VOLTRON', 'Invalid selection')
				return False

			selected_user = User(account_list[selection-1])
			callback(selected_user)
			self.update_status_text()
			return True


		self.update_status_text('Select account. c to cancel.')
		self.get_prompt('Account Number> ', selection_made)
		return selected_user

	def list_accounts(self, input=None, command=None):
		users = get_all_acccounts()
		count = 1
		self.buffer_print('VOLTRON', '')
		account_list = []
		for user in users:
			output_str = '{num}. {display} default={default} broadcaster={broadcaster}'.format(
				num = count,
				display = user.display_name,
				channel = user.user_name,
				default = user.is_default,
				broadcaster = user.is_broadcaster
			)
			account_list.append(user.id)
			self.buffer_print('VOLTRON', output_str)
			count += 1
		self.buffer_print('VOLTRON', '')
		return account_list

	@property
	def data_directory(self):
		if not hasattr(self, 'module_name'):
			return None
		return get_module_data_directory(self.module_name)
