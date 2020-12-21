from base.module import ModuleBase, ModuleAdminCommand
from base.events import EVT_CHATCOMMAND
from lib.common import get_user_by_twitch_id
import re
import time

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
			'appendcommand': self._append_command,
			'deletecommand': self._delete_command,
			#'c': self._list_commands,
		}

		self.register_admin_command(ModuleAdminCommand(
			'list',
			self.list_commands,
			usage = f'{self.module_name} list',
			description = 'List all basic commands'
		))

		self.register_admin_command(ModuleAdminCommand(
			'details',
			self.command_details,
			usage = f'{self.module_name} details !<command>',
			description = 'Show details of !<command>'
		))

		self.register_admin_command(ModuleAdminCommand(
			'command_account',
			self.command_account,
			usage = f'{self.module_name} command_account !<command>',
			description = 'Change the response account for !<command>'
		))

		self.register_admin_command(ModuleAdminCommand(
			'mod_only',
			self.toggle_mod_only,
			usage = f'{self.module_name} mod_only !<command>',
			description = 'Toggle mod only permission for command'
		))

		self.register_admin_command(ModuleAdminCommand(
			'broadcaster_only',
			self.toggle_broadcaster_only,
			usage = f'{self.module_name} broadcaster_only !<command>',
			description = 'Toggle broadcaster only permission for command'
		))

		self.register_admin_command(ModuleAdminCommand(
			'counters',
			self.list_counters,
			usage = f'{self.module_name} counters',
			description = 'List all counters'
		))

		self.register_admin_command(ModuleAdminCommand(
			'set_counter',
			self._set_counter,
			usage = f'{self.module_name} set_counter <counter_name> <value>',
			description = 'Set value of a counter'
		))

		self.event_listen(EVT_CHATCOMMAND, self.command)

	def command(self, event):
		## Chat command received
		if event.command in self._static_commands:
			self._static_commands[event.command](event)
			return False

		elif event.command in self._commands:
			if self._commands[event.command].get('broadcaster_only', False) and not event.is_broadcaster:
				return False
			if self._commands[event.command].get('mod_only', False) and not event.is_mod:
				return False

			twitch_id = self._commands[event.command].get('response_twitch_id', None)

			for response in self._commands[event.command]['response']:
				self.send_chat_message(response, twitch_id=twitch_id, event=event)

			self.save_module_data(self._commands)

			return True

	def _list_commands(self, event):
		commands = self.event_loop.get_all_commands(event.user_id, event.is_mod, event.is_broadcaster)
		commands_str = ', '.join(commands['basic_commands'])
		self.send_private_message(event.display_name, commands_str)

	def _add_command(self, event):
		if not event.is_mod:
			self.send_chat_message(f"@{event.display_name} you are not a mod.")
			return

		match = re.search(r'^!([^ ]+) (.*)', event.args)
		if match:
			command = match.group(1)
			response = match.group(2).strip()
			if command in self._commands:
				#self._commands[command]['response'] = [response]
				self.send_chat_message(f"@{event.display_name} The command !{command} already exists. You can delete it using !deletecommand")
				return
			else:
				self._commands[command] = { 'response': [response] }

			self.save_module_data(self._commands)
			self.send_chat_message(f'Command !{command} successfully added!')

	def _append_command(self, event):
		if not event.is_mod:
			self.send_chat_message(f"@{event.display_name} you are not a mod.")
			return

		match = re.search(r'^!([^ ]+) (.*)', event.args)
		if match:
			command = match.group(1)
			response = match.group(2).strip()

			if not command in self._commands:
				self.send_chat_message(f'Command !{command} not found')
				return

			self._commands[command]['response'].append(response)
			self.save_module_data(self._commands)
			self.send_chat_message(f'Command !{command} successfully modified')


	def _delete_command(self, event):
		if not event.is_mod:
			self.send_chat_message(f"@{event.display_name} you are not a mod.")
			return
		match = re.search(r'^!([^ ]+)$', event.args)
		if not match:
			self.send_chat_message('Usage: !deletecommand <command>')
			return

		command = match.group(1)
		if not command in  self._commands.keys():
			self.send_chat_message(f'Command !{command} not found')
			return

		del self._commands[command]
		self.save_module_data(self._commands)
		self.send_chat_message(f'Command !{command} successfully deleted!')

	def toggle_mod_only(self, input, command):
		match = re.search(r'^!([^ ]+)$', input)
		if not match:
			self.buffer_print('VOLTRON', f'Usage: {command.usage}')
			return

		command = match.group(1)
		if not command in self._commands:
			self.buffer_print('VOLTRON', f'Command !{command} does not exist')
			return

		mod_only = self._commands[command].get('mod_only', False)

		mod_only = not mod_only
		self._commands[command]['mod_only'] = mod_only
		self.save_module_data(self._commands)

		self.buffer_print('VOLTRON', f'Permission changed for !{command} (mod_only={mod_only})')

	def toggle_broadcaster_only(self, input, command):
		match = re.search(r'^!([^ ]+)$', input)
		if not match:
			self.buffer_print('VOLTRON', f'Usage: {command.usage}')
			return

		command = match.group(1)
		if not command in self._commands:
			self.buffer_print('VOLTRON', f'Command !{command} does not exist')
			return

		broadcaster_only = self._commands[command].get('broadcaster_only', False)

		broadcaster_only = not broadcaster_only
		self._commands[command]['broadcaster_only'] = broadcaster_only
		self.save_module_data(self._commands)

		self.buffer_print('VOLTRON', f'Permission changed for !{command} (broadcaster_only={broadcaster_only})')

	def command_account(self, input, command):
		match = re.search(r'^!([^ ]+)$', input)
		if not match:
			self.buffer_print('VOLTRON', f'Usage: {command.usage}')
			return

		command = match.group(1)
		if not command in self._commands:
			self.buffer_print('VOLTRON', f'Command !{command} does not exist')
			return

		def account_selected(account):
			self._commands[command]['response_twitch_id'] = account.twitch_user_id
			self.save_module_data(self._commands)

		self.select_account(account_selected)

	def list_commands(self, input, command):
		self.buffer_print('VOLTRON', '')
		self.buffer_print('VOLTRON', f'Available commands in {self.module_name} module:')
		self._print_commands()
		self.buffer_print('VOLTRON', '')

	def list_counters(self, input, command):
		self.buffer_print('VOLTRON', 'All counters:')
		counters = self.get_all_counters()

		for counter in counters:
			self.buffer_print('VOLTRON', f"  {counter['counter_name']}: {counter['value']}")

	def _set_counter(self, input, command):
		match = re.search(r'^([^ ]+) ([\d]+)$', input)
		if not match:
			self.buffer_print('VOLTRON', f'Usage: {command.usage}')
			return

		counter_name = match.group(1)
		value = int(match.group(2))

		counter = self.get_counter(counter_name)
		if not counter:
			self.buffer_print('VOLTRON', f'Counter does not exsit: {counter_name}')
			return

		self.set_counter(counter_name, value)
		self.buffer_print('VOLTRON', f'Counter {counter_name} set to {value}')


	def command_details(self, input, command):
		match = re.search(r'^!([^ ]+)$', input)

		if not match:
			self.buffer_print('VOLTRON', f'Usage: {command.usage}')
			return

		command = match.group(1)
		if not command in self._commands:
			self.buffer_print('VOLTRON', f'Unknown command: !{command}')
			return

		mod_only = self._commands[command].get('mod_only', False)
		broadcaster_only = self._commands[command].get('broadcaster_only', False)
		twitch_id = self._commands[command].get('response_twitch_id', None)
		twitch_user_name = "Default"
		if twitch_id:
			user = get_user_by_twitch_id(twitch_id)
			if user:
				twitch_user_name = user.display_name

		self.buffer_print('VOLTRON', f'Details for command !{command}:')
		self.buffer_print('VOLTRON', f'  Response Account: {twitch_user_name}')
		self.buffer_print('VOLTRON', f'  Mod Only: {mod_only}')
		self.buffer_print('VOLTRON', f'  Broadcaster Only: {broadcaster_only}')
		self.buffer_print('VOLTRON',  '  Response:')

		for line in self._commands[command]['response']:
			self.buffer_print('VOLTRON', f'    {line}')

	def _print_commands(self):
		for command in sorted(self._commands):
			output_str = "  !{command}".format(
				command = command
			)
			if self._commands[command].get('broadcaster_only', False):
				output_str += ' (broadcaster only)'
			if self._commands[command].get('mod_only', False):
				output_str += ' (mod only)'

			self.buffer_print('VOLTRON', output_str)

	def shutdown(self):
		self.save_module_data(self._commands)
