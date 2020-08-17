from base.module import ModuleBase, ModuleAdminCommand
from base.events import EVT_CHATCOMMAND
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
		self._default_cooldown = 10

		self._static_commands = {
			'addcommand': self._add_command,
			'deletecommand': self._delete_command
		}

		self.register_admin_command(ModuleAdminCommand(
			'list',
			self.list_commands,
			usage = 'basic_commands list',
			description = 'List all basic commands'
		))

		self.register_admin_command(ModuleAdminCommand(
			'command_account',
			self.command_account,
			usage = 'basic_commands command_account !<command>',
			description = 'Change the response account for !<command>'
		))

		self.register_admin_command(ModuleAdminCommand(
			'mod_only',
			self.toggle_mod_only,
			usage = 'basic_commands mod_only !<command>',
			description = 'Toggle mod only permission for command'
		))

		self.register_admin_command(ModuleAdminCommand(
			'broadcaster_only',
			self.toggle_broadcaster_only,
			usage = 'basic_commands broadcaster_only !<command>',
			description = 'Toggle broadcaster only permission for command'
		))

		self.register_admin_command(ModuleAdminCommand(
			'cooldowns',
			self.set_cooldowns,
			usage = 'basic_commands cooldowns !<command> <global cooldown> <user cooldown>',
			description = 'Set the global and user cooldown for !<command> in seconds.'
		))

		self.event_listen(EVT_CHATCOMMAND, self.command)

	def command(self, event):
		## Chat command received
		if event.command in self._static_commands:
			self._static_commands[event.command](event)
			return

		elif event.command in self._commands:
			if self._commands[event.command].get('broadcaster_only', False) and not event.is_broadcaster:
				return
			if self._commands[event.command].get('mod_only', False) and not event.is_mod:
				return

			if not 'runtime' in self._commands[event.command]:
				self._commands[event.command]['runtime'] = {
					'global': 0,
					'user': {}
				}

			twitch_id = self._commands[event.command].get('response_twitch_id', None)

			## check user cooldown
			user_elapsed = time.time() - self._commands[event.command]['runtime']['user'].get(event.user_id, 0)
			user_cooldown = self._commands[event.command].get('user_cooldown', self._default_cooldown)
			if user_elapsed < user_cooldown:
				remaining = user_cooldown - user_elapsed
				self.send_chat_message("Command !{command} is on cooldown ({remaining}s)".format(
					command = event.command,
					remaining = int(remaining)
				), twitch_id)
				return

			## check global cooldown
			global_elapsed = time.time() - self._commands[event.command]['runtime']['global']
			global_cooldown = self._commands[event.command].get('global_cooldown', self._default_cooldown)
			if global_elapsed < global_cooldown:
				remaining = global_cooldown - global_elapsed
				self.send_chat_message("Command !{command} is on cooldown ({remaining}s)".format(
					command = event.command,
					remaining = int(remaining)
				), twitch_id)
				return

			self.send_chat_message(self._commands[event.command]['response'], twitch_id)
			self._commands[event.command]['runtime']['global'] = time.time()
			self._commands[event.command]['runtime']['user'][event.user_id] = time.time()

	def _add_command(self, event):
		if not event.is_mod:
			self.send_chat_message("@{} you are not a mod.".format(event.display_name))
			return

		match = re.search(r'^!([^ ]+) (.*)', event.args)
		if match:
			command = match.group(1)
			response = match.group(2).strip()
			if command in self._commands:
				self._commands[command]['response'] = response
			else:
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

	def set_cooldowns(self, input):
		match = re.search(r'^!([^ ]+) ([0-9]+) ([0-9]+)$', input)
		if not match:
			self.buffer_print('VOLTRON', 'Invalid paramaters')
			self.buffer_print('VOLTRON', 'Usage: !<command> <global_cooldown> <user_cooldown>')
			return

		command = match.group(1)
		if not command in self._commands:
			self.buffer_print('VOLTRON', 'Command !{} does not exist'.format(command))
			return

		global_cooldown = int(match.group(2))
		user_cooldown = int(match.group(3))

		self._commands[command]['global_cooldown'] = global_cooldown
		self._commands[command]['user_cooldown'] = user_cooldown

		self.buffer_print('VOLTRON', 'Cooldowns set for command !{}'.format(command))
		self.buffer_print('VOLTRON', 'global = {}'.format(global_cooldown))
		self.buffer_print('VOLTRON', 'user = {}'.format(user_cooldown))

	def toggle_mod_only(self, input):
		match = re.search(r'^!([^ ]+)$', input)
		if not match:
			self.buffer_print('VOLTRON', 'Must include command')
			return

		command = match.group(1)
		if not command in self._commands:
			self.buffer_print('VOLTRON', 'Command !{} does not exist'.format(command))
			return

		mod_only = self._commands[command].get('mod_only', False)

		mod_only = not mod_only
		self._commands[command]['mod_only'] = mod_only
		self.save_module_data(self._commands)

		self.buffer_print('VOLTRON', 'Permission changed for !{command} (mod_only={mod_only})'.format(
			command = command,
			mod_only = mod_only
		))

	def toggle_broadcaster_only(self, input):
		match = re.search(r'^!([^ ]+)$', input)
		if not match:
			self.buffer_print('VOLTRON', 'Must include command')
			return

		command = match.group(1)
		if not command in self._commands:
			self.buffer_print('VOLTRON', 'Command !{} does not exist'.format(command))
			return

		broadcaster_only = self._commands[command].get('broadcaster_only', False)

		broadcaster_only = not broadcaster_only
		self._commands[command]['broadcaster_only'] = broadcaster_only
		self.save_module_data(self._commands)

		self.buffer_print('VOLTRON', 'Permission changed for !{command} (broadcaster_only={broadcaster_only})'.format(
			command = command,
			broadcaster_only = broadcaster_only
		))


	def command_account(self, input):
		match = re.search(r'^!([^ ]+)$', input)
		if not match:
			self.buffer_print('VOLTRON', 'Must include command')
			return

		command = match.group(1)
		if not command in self._commands:
			self.buffer_print('VOLTRON', 'Command !{} does not exist'.format(command))
			return

		def account_selected(account):
			self._commands[command]['response_twitch_id'] = account.twitch_user_id
			self.save_module_data(self._commands)

		self.select_account(account_selected)

	def list_commands(self, input):
		self.buffer_print('VOLTRON', '')
		self.buffer_print('VOLTRON', 'Available commands in basic_command module:')
		self._print_commands()
		self.buffer_print('VOLTRON', '')

	def remove_expired_cooldowns(self):
		for command in self._commands:
			user_cooldown = self._commands[command].get('user_cooldown', self._default_cooldown)
			user_cooldowns = {}
			if not 'runtime' in self._commands[command] or not 'user' in self._commands[command]['runtime']:
				continue

			for user_id in self._commands[command]['runtime']['user']:
				if (time.time() - self._commands[command]['runtime']['user'][user_id]) < user_cooldown:
					user_cooldowns[user_id] = self._commands[command]['runtime']['user']

			self._commands[command]['runtime']['user'] = user_cooldowns

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
		self.remove_expired_cooldowns()
		self.save_module_data(self._commands)
