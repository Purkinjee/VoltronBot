from base.module import ModuleBase, ModuleAdminCommand
from base.events import EVT_CHATCOMMAND
import re

class BasicCommands(ModuleBase):
	"""
	Basic Command module. This module will repsond in chat to commands begginging with !
	"""
	module_name = 'basic_commands'
	def setup(self):
		## Commands are saved in the database
		self._commands = self.get_module_data()

		self._static_commands = {
			'addcommand': self._add_command,
			'deletecommand': self._delete_command
		}

		self.event_listen(EVT_CHATCOMMAND, self.command)

	def command(self, event):
		## Chat command received
		if event.command in self._static_commands:
			self._static_commands[event.command](event)
			return

		elif event.command in self._commands:
			self.send_chat_message(self._commands[event.command]['response'])

	def _add_command(self, event):
		if not event.is_mod:
			self.send_chat_message("@{} you are not a mod.".format(event.display_name))
			return

		match = re.search(r'^!([^ ]+) (.*)', event.args)
		if match:
			command = match.group(1)
			response = match.group(2).strip()
			self._commands[command] = { 'response': response }

			self.save_module_data(self._commands)
			self.send_chat_message('Command !{} successfully added!'.format(command))

	def _delete_command(self, event):
		if not event.is_mod:
			self.send_chat_message("@{} you are not a mod.".format(event.display_name))
			return
		match = re.search(r'^!([^ ]+)$', event.args)
		if not match:
			self.send_chat_message('Usage: !deletecommand <command>')
			return

		command = match.group(1)
		if not command in  self._commands.keys():
			self.send_chat_message('Command !{} not found'.format(command))
			return

		del self._commands[command]
		self.save_module_data(self._commands)
		self.send_chat_message('Command !{} successfully deleted!'.format(command))

	def shutdown(self):
		self.save_module_data(self._commands)
