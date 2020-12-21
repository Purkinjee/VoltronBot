from base.module import ModuleBase, ModuleAdminCommand
from base.events import EVT_CHATCOMMAND

import re
import time

class CooldownModule(ModuleBase):
	module_name = 'cooldown'
	def setup(self):
		self._cooldown_data = self.get_module_data()

		if not 'commands' in self._cooldown_data:
			self._cooldown_data['commands'] = {}
		if not 'runtimes' in self._cooldown_data:
			self._cooldown_data['runtimes'] = {}

		self.register_admin_command(ModuleAdminCommand(
			'list',
			self._list_cooldowns,
			usage = f'{self.module_name} list',
			description = 'List cooldowns'
		))

		self.register_admin_command(ModuleAdminCommand(
			'default_cooldown',
			self._set_default_cooldown,
			usage = f'{self.module_name} default_cooldown <time>',
			description = 'Set the default cooldown for all commands in seconds'
		))

		self.register_admin_command(ModuleAdminCommand(
			'set',
			self._set_cooldown,
			usage = f'{self.module_name} set !<command> <global> <user>',
			description = 'Set the global and user cooldowns for !<command> in seconds'
		))

		self.register_admin_command(ModuleAdminCommand(
			'notifications',
			self._set_notifications,
			usage = f'{self.module_name} notifications <on/off>',
			description = 'Enable or disable cooldown notifications in Twitch chat'
		))

		self.register_admin_command(ModuleAdminCommand(
			'delete',
			self._delete_cooldown,
			usage = f'{self.module_name} delete !<command>',
			description = 'Delete cooldowns for !<command>'
		))

		#self.event_listen(EVT_CHATCOMMAND, self.command)

	def command(self, event):
		if not event.command in self._cooldown_data['commands']:
			return

		runtimes = self._cooldown_data['runtimes'].get(event.command, {})
		user_runtimes = runtimes.get('user', {})

		runtimes['global'] = time.time()
		user_runtimes[event.user_id] = time.time()
		runtimes['user'] = user_runtimes
		self._cooldown_data['runtimes'][event.command] = runtimes

	def update_runtimes(self, event):
		runtimes = self._cooldown_data['runtimes'].get(event.command, {})
		user_runtimes = runtimes.get('user', {})

		runtimes['global'] = time.time()
		user_runtimes[event.user_id] = time.time()
		runtimes['user'] = user_runtimes
		self._cooldown_data['runtimes'][event.command] = runtimes

		self.save_module_data(self._cooldown_data)

	def event_on_cooldown(self, event):
		if not event.command in self._cooldown_data['runtimes']:
			return False

		if not event.command in self._cooldown_data['commands'] and not self.default_cooldown:
			return False

		global_cd = self.default_cooldown
		user_cd = 0

		if event.command in self._cooldown_data['commands']:
			global_cd = self._cooldown_data['commands'][event.command]['global']
			user_cd = self._cooldown_data['commands'][event.command]['user']

		runtimes = self._cooldown_data['runtimes'].get(event.command, {})
		user_runtime = runtimes.get('user', {}).get(event.user_id, 0)
		global_runtime = runtimes.get('global', 0)

		user_diff = time.time() - user_runtime
		global_diff = time.time() - global_runtime
		if (user_diff < user_cd) or (global_diff < global_cd):
			cd = int(max((user_cd - user_diff), (global_cd - global_diff)))
			if self._cooldown_data.get('notifications', True):
				self.send_chat_message(f'@{{sender}}: Command !{event.command} is on cooldown. ({cd}s)', event=event)
			return True

		return False

	def _set_default_cooldown(self, input, command):
		if not input.isdigit():
			self.buffer_print('VOLTRON', f'Usage: {command.usage}')
			self.buffer_print('VOLTRON', f'Current default: {self.default_cooldown}s')
			return

		default_cd = int(input)
		self._cooldown_data['default_cooldown'] = default_cd
		self.save_module_data(self._cooldown_data)
		self.buffer_print('VOLTRON', f'Default cooldown set to {default_cd}s')

	def _set_cooldown(self, input, command):
		match = re.search(r'^!([^ ]+) (\d+) (\d+)$', input)
		if not match:
			self.buffer_print('VOLTRON', f'Usage: {command.usage}')
			return

		command = match.group(1)
		global_cd = int(match.group(2))
		user_cd = int(match.group(3))

		cd_data = self._cooldown_data['commands'].get(command, {})
		cd_data['global'] = global_cd
		cd_data['user'] = user_cd

		self._cooldown_data['commands'][command] = cd_data

		self.save_module_data(self._cooldown_data)

		self.buffer_print('VOLTRON', f'Cooldown set for !{command}')
		self.buffer_print('VOLTRON', f'  Global: {global_cd}s')
		self.buffer_print('VOLTRON', f'  User: {user_cd}s')

	def _set_notifications(self, input, command):
		if not input.strip().lower() in ('on', 'off'):
			self.buffer_print('VOLTRON', f'Usage: {command.usage}')
			return

		enabled = input.strip().lower() == 'on'

		self._cooldown_data['notifications'] = enabled
		self.save_module_data(self._cooldown_data)

		self.buffer_print('VOLTRON', f'Cooldown notifications turned {input.strip().lower()}')

	def _delete_cooldown(self, input, command):
		match = re.search(r'^!([^ ]+)$', input)
		if not match:
			self.buffer_print('VOLTRON', f'Usage: {command.usage}')
			return

		command = match.group(1)

		if not command in self._cooldown_data['commands']:
			self.buffer_print('VOLTRON', f'Cooldowns for command !{command} not set')
			return

		del self._cooldown_data['commands'][command]

		if command in self._cooldown_data['runtimes']:
			del self._cooldown_data['runtimes'][command]

		self.save_module_data(self._cooldown_data)

		self.buffer_print('VOLTRON', f'Cooldowns for command !{command} successfully removed.')

	def _list_cooldowns(self, input, command):
		for command in self._cooldown_data['commands']:
			command_data = self._cooldown_data['commands'][command]
			self.buffer_print('VOLTRON', f'!{command}:')
			self.buffer_print('VOLTRON', f"  Global: {command_data['global']}s")
			self.buffer_print('VOLTRON', f"  User: {command_data['user']}s")

	def remove_expired_cooldowns(self):
		for command in self._cooldown_data['commands']:
			user_cd = self._cooldown_data['commands'][command]['user']
			user_cooldowns = {}
			if not command in self._cooldown_data['runtimes'] or not 'user' in self._cooldown_data['runtimes'][command]:
				continue

			for user_id in self._cooldown_data['runtimes'][command]['user']:
				if (time.time() - self._cooldown_data['runtimes'][command]['user'][user_id]) < user_cd:
					user_cooldowns[user_id] = self._cooldown_data['runtimes'][command]['user'][user_id]

			self._cooldown_data['runtimes'][command]['user'] = user_cooldowns

	def shutdown(self):
		self.remove_expired_cooldowns()
		self.save_module_data(self._cooldown_data)

	@property
	def default_cooldown(self):
		return self._cooldown_data.get('default_cooldown', 0)
