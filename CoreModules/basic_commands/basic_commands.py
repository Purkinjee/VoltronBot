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
			'add',
			self._add_command_admin,
			usage = f'{self.module_name} add !<command> [reply=<True/False>] <response> ',
			description = 'Add a basic command.'
		))

		self.register_admin_command(ModuleAdminCommand(
			'append',
			self._append_command_admin,
			usage = f'{self.module_name} append !<command> [reply=<True/False>] <response>',
			description = 'Append a response to an existing command'
		))

		self.register_admin_command(ModuleAdminCommand(
			'delete',
			self._delete_command_admin,
			usage = f'{self.module_name} delete !<command>',
			description = 'Delete a command'
		))

		self.register_admin_command(ModuleAdminCommand(
			'toggle',
			self._toggle_command,
			usage = f'{self.module_name} toggle !<command>',
			description = 'Enable or disable !<command>'
		))

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
			if not self._commands[event.command].get('enabled', True):
				return
			twitch_id = self._commands[event.command].get('response_twitch_id', None)

			for response in self._commands[event.command]['response']:
				if not type(response) is list:
					self._commands[event.command]['response'].remove(response)
					self._commands[event.command]['response'].append([response,False])
					self.send_chat_message(response,twitch_id=twitch_id,event=event,reply=False)
    			else:	
					self.send_chat_message(response[0], twitch_id=twitch_id, event=event,reply=response[1])
			
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
		if '[reply=' in event.message:
			match = re.search(r'^!([^ ]+) \[(.*?)\] (.*)', event.message)
		else:
			match = re.search(r'^!([^ ]+) (.*)', event.message)
		if match:
			command = match.group(1)
			if len(match.groups()) == 2:
				response = match.group(2).strip()
				reply = False
			else:
				response = match.group(3).strip()
				if "true" in match.group(2).lower:
					reply = True
				else:
					reply = False
					
			if command in self._commands:
				#self._commands[command]['response'] = [response]
				self.send_chat_message(f"@{event.display_name} The command !{command} already exists. You can delete it using !deletecommand")
				return
			else:
				self._commands[command] = { 'response': [[response,reply]] }
			
			self.save_module_data(self._commands)
			self.send_chat_message(f'Command !{command} successfully added!')

	def _add_command_admin(self, input, command):
		#match = re.search(r'^!([^ ]+) (.*)', input)
 
		match = re.search(r'^!([^ ]+) \[(.*?)\] (.*)', input)
		
			
		if not match:
			self.print(f'Usage: {command.usage}')
			return

		new_command = match.group(1)
		if len(match.groups()) == 2:
			response = match.group(2).strip()
			reply = False
		else:
			response = match.group(3).strip()
			if "true" in match.group(2).lower():
				reply = True
			else:
				reply = False
   
		if new_command in self._commands:
			self.print(f'The command !{new_command} already exists')
			return
		else:
			
   			self._commands[new_command] = { 'response': [[response,reply]], }
			
		self.save_module_data(self._commands)
		self.print(f'Command !{new_command} successfully added!')

	def _append_command(self, event):
		if not event.is_mod:
			self.send_chat_message(f"@{event.display_name} you are not a mod.")
			return
		match = re.search(r'^!([^ ]+) \[(.*?)\] (.*)', event.message)


		if match:
			command = match.group(1)
			if not command in self._commands:
				self.send_chat_message(f'Command !{command} not found')
				return
   
			if len(match.groups()) == 2:
				response = match.group(2).strip()
				reply = False
			else:
				response = match.group(3).strip()
				if "true" in match.group(2).lower():
					reply = True
				else: 
					reply = False

			
			self._commands[command]['response'].append([response,reply])
			self.save_module_data(self._commands)
			self.send_chat_message(f'Command !{command} successfully modified')

	def _append_command_admin(self, input, command):
		match = re.search(r'^!([^ ]+) \[(.*?)\] (.*)', input)
		if not match:
			self.print(f'Usage: {command.usage}')
			return

		new_command = match.group(1)
		if len(match.groups()) == 2:
			response = match.group(2)
			reply = False
		else:
			response = match.group(3)
			if "true" in match.group(2):
				reply = True
			else:
				reply = False

		if not new_command in self._commands:
			self.print(f'Command !{new_command} not found')
			return

		self._commands[new_command]['response'].append([response,reply])
		self.save_module_data(self._commands)
		self.print(f'Command !{new_command} successfully modified')


	def _delete_command(self, event):
		if not event.is_mod:
			self.send_chat_message(f"@{event.display_name} you are not a mod.")
			return
		match = re.search(r'^!([^ ]+)$', event.message)
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

	def _delete_command_admin(self, input, command):
		match = re.search(r'^!([^ ]+)$', input)
		if not match:
			self.print(f'Usage: {command.usage}')
			return

		new_command = match.group(1)
		if not new_command in  self._commands.keys():
			self.print(f'Command !{new_command} not found')
			return

		del self._commands[new_command]
		self.save_module_data(self._commands)
		self.print(f'Command !{new_command} successfully deleted!')

	def _toggle_command(self, input, command):
		match = re.search(r'^!([^ ]+)$', input)
		if not match:
			self.print(f'Usage: {command.usage}')
			return

		toggle_command = match.group(1)
		if not toggle_command in self._commands.keys():
			self.print(f'Command !{toggle_command} not found')
			return

		enabled = not self._commands[toggle_command].get('enabled', True)
		self._commands[toggle_command]['enabled'] = enabled
		self.save_module_data(self._commands)

		enabled_str = "Enabled" if enabled else "Disabled"
		self.print(f"!{toggle_command} has been {enabled_str}")

	def command_account(self, input, command):
		match = re.search(r'^!([^ ]+)$', input)
		if not match:
			self.print(f'Usage: {command.usage}')
			return

		command = match.group(1)
		if not command in self._commands:
			self.print(f'Command !{command} does not exist')
			return

		def account_selected(account):
			self._commands[command]['response_twitch_id'] = account.twitch_user_id
			self.save_module_data(self._commands)

		self.select_account(account_selected)

	def list_commands(self, input, command):
		self.print('')
		self.print(f'Available commands in {self.module_name} module:')
		self._print_commands()
		self.print('')

	def list_counters(self, input, command):
		self.print('All counters:')
		counters = self.get_all_counters()

		for counter in counters:
			self.print(f"  {counter['counter_name']}: {counter['value']}")

	def _set_counter(self, input, command):
		match = re.search(r'^([^ ]+) ([\d]+)$', input)
		if not match:
			self.print(f'Usage: {command.usage}')
			return

		counter_name = match.group(1)
		value = int(match.group(2))

		counter = self.get_counter(counter_name)
		if not counter:
			self.print(f'Counter does not exsit: {counter_name}')
			return

		self.set_counter(counter_name, value)
		self.print(f'Counter {counter_name} set to {value}')


	def command_details(self, input, command):
		match = re.search(r'^!([^ ]+)$', input)

		if not match:
			self.print(f'Usage: {command.usage}')
			return

		command = match.group(1)
		if not command in self._commands:
			self.print(f'Unknown command: !{command}')
			return

		twitch_id = self._commands[command].get('response_twitch_id', None)
		twitch_user_name = "Default"
		if twitch_id:
			user = get_user_by_twitch_id(twitch_id)
			if user:
				twitch_user_name = user.display_name

		self.print(f'Details for command !{command}:')
		self.print(f'  Response Account: {twitch_user_name}')
		self.print('  Response:')
		

		for line in self._commands[command]['response']:
			self.print(f'    {line[0]}')

	def _print_commands(self):
		for command in sorted(self._commands):
			enabled = self._commands[command].get('enabled', True)
			output_str = "  !{command}".format(
				command = command
			)
			if not enabled:
				output_str += " (disabled)"

			self.print(output_str)

	def shutdown(self):
		self.save_module_data(self._commands)
