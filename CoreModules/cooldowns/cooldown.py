from base.module import ModuleBase, ModuleAdminCommand
from base.events import EVT_CHATCOMMAND

import re
import time
import threading

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
			usage = f'{self.module_name} set !<command> <global> <user> <queue>',
			description = 'Set the global and user cooldowns for !<command> in seconds. <queue> can be yes/no. Defaults to yes.'
		))

		self.register_admin_command(ModuleAdminCommand(
			'notifications',
			self._set_notifications,
			usage = f'{self.module_name} notifications <on/off>',
			description = 'Enable or disable cooldown notifications in Twitch chat'
		))

		self.register_admin_command(ModuleAdminCommand(
			'notification_override',
			self._notification_override,
			usage = f'{self.module_name} notification_override <!command> <on/off/inherit>',
			description = 'Enable or disable cooldown notification for a specific command'
		))

		self.register_admin_command(ModuleAdminCommand(
			'delete',
			self._delete_cooldown,
			usage = f'{self.module_name} delete !<command>',
			description = 'Delete cooldowns for !<command>'
		))

		self.event_listen(EVT_CHATCOMMAND, self.command)

	def command(self, event):
		if event.bypass_cooldowns:
			return

		if not event.command in self._cooldown_data['commands']:
			return

		runtimes = self._cooldown_data['runtimes'].get(event.command, {})
		user_runtimes = runtimes.get('user', {})

		runtimes['global'] = time.time()
		user_runtimes[event.user_id] = time.time()
		runtimes['user'] = user_runtimes
		self._cooldown_data['runtimes'][event.command] = runtimes

	def update_runtimes(self, event):
		if event.bypass_cooldowns:
			return

		runtimes = self._cooldown_data['runtimes'].get(event.command, {})
		user_runtimes = runtimes.get('user', {})

		runtimes['global'] = time.time()
		user_runtimes[event.user_id] = time.time()
		runtimes['user'] = user_runtimes
		self._cooldown_data['runtimes'][event.command] = runtimes

		self.save_module_data(self._cooldown_data)

	def event_on_cooldown(self, event):
		if event.bypass_cooldowns:
			return False
		if event.is_broadcaster:
			return False
		if not event.command in self._cooldown_data['runtimes']:
			return False

		if not event.command in self._cooldown_data['commands'] and not self.default_cooldown:
			return False

		global_cd = self.default_cooldown
		user_cd = 0
		notify = self._cooldown_data.get('notifications', True)

		if event.command in self._cooldown_data['commands']:
			cd_data = self._cooldown_data['commands'][event.command]
			global_cd = cd_data.get('global', global_cd)
			user_cd = cd_data.get('user', user_cd)
			notify = cd_data.get('notification', notify)

		runtimes = self._cooldown_data['runtimes'].get(event.command, {})
		user_runtime = runtimes.get('user', {}).get(event.user_id, 0)
		global_runtime = runtimes.get('global', 0)

		user_diff = time.time() - user_runtime
		global_diff = time.time() - global_runtime
		if (user_diff < user_cd) or (global_diff < global_cd):
			cd = max((user_cd - user_diff), (global_cd - global_diff))
			self.print(cd)
			to_queue = cd_data.get('queue', False)
			if notify and not to_queue:
				self.send_chat_message(f'@{{sender}}: Command !{event.command} is on cooldown. ({int(cd)}s)', event=event)
			if to_queue:
				runtimes = self._cooldown_data['runtimes'].get(event.command, {})
				user_runtimes = runtimes.get('user', {})

				runtimes['global'] = time.time() + cd
				user_runtimes[event.user_id] = time.time() + cd
				runtimes['user'] = user_runtimes
				self._cooldown_data['runtimes'][event.command] = runtimes

				self.save_module_data(self._cooldown_data)

				thread = threading.Thread(target=self._queue_command, args=(event, cd))
				thread.start()

				return True
			else:
				return True

		return False

	def _queue_command(self, event, delay):
		time.sleep(delay)
		event.bypass_cooldowns = True
		self.event_loop.event_queue.put(event)

	def _set_default_cooldown(self, input, command):
		if not input.isdigit():
			self.print(f'Usage: {command.usage}')
			self.print(f'Current default: {self.default_cooldown}s')
			return

		default_cd = int(input)
		self._cooldown_data['default_cooldown'] = default_cd
		self.save_module_data(self._cooldown_data)
		self.print(f'Default cooldown set to {default_cd}s')

	def _set_cooldown(self, input, command):
		match = re.search(r'^!([^ ]+) (\d+) (\d+)( (yes|no))?$', input)
		if not match:
			self.print(f'Usage: {command.usage}')
			return

		command = match.group(1)
		global_cd = int(match.group(2))
		user_cd = int(match.group(3))
		queue = True if str(match.group(5)).lower() == 'yes' else False
		queue_str = 'Yes' if queue else 'No'

		cd_data = self._cooldown_data['commands'].get(command, {})
		cd_data['global'] = global_cd
		cd_data['user'] = user_cd
		cd_data['queue'] = queue

		self._cooldown_data['commands'][command] = cd_data

		self.save_module_data(self._cooldown_data)

		self.print(f'Cooldown set for !{command}')
		self.print(f'  Global: {global_cd}s')
		self.print(f'  User: {user_cd}s')
		self.print(f'  Queue: {queue_str}')

	def _set_notifications(self, input, command):
		if not input.strip().lower() in ('on', 'off'):
			self.print(f'Usage: {command.usage}')
			return

		enabled = input.strip().lower() == 'on'

		self._cooldown_data['notifications'] = enabled
		self.save_module_data(self._cooldown_data)

		self.print(f'Cooldown notifications turned {input.strip().lower()}')

	def _notification_override(self, input, command):
		match = re.search(r'^!([^ ]+) (on|off|inherit)$', input)
		if not match:
			self.print(f'Usage: {command.usage}')
			return

		cd_command = match.group(1)
		action = {
			'on': True,
			'off': False,
			'inherit': None
		}[match.group(2)]
		self.print(cd_command)
		self.print(action)

		cd_data = self._cooldown_data['commands'].get(cd_command, {})
		if 'notification' in cd_data and action is None:
			del cd_data['notification']
		else:
			cd_data['notification'] = action

		if not cd_data:
			del self._cooldown_data['commands'][cd_command]
		else:
			self._cooldown_data['commands'][cd_command] = cd_data

		self.save_module_data(self._cooldown_data)
		self.print(f'Notification for !{cd_command} set to {match.group(2)}')

	def _delete_cooldown(self, input, command):
		match = re.search(r'^!([^ ]+)$', input)
		if not match:
			self.print(f'Usage: {command.usage}')
			return

		command = match.group(1)

		if not command in self._cooldown_data['commands']:
			self.print(f'Cooldowns for command !{command} not set')
			return

		del self._cooldown_data['commands'][command]

		if command in self._cooldown_data['runtimes']:
			del self._cooldown_data['runtimes'][command]

		self.save_module_data(self._cooldown_data)

		self.print(f'Cooldowns for command !{command} successfully removed.')

	def _list_cooldowns(self, input, command):
		for command in self._cooldown_data['commands']:
			command_data = self._cooldown_data['commands'][command]
			self.print(f'!{command}:')
			if 'global' in command_data:
				self.print(f"  Global: {command_data['global']}s")
			if 'user' in command_data:
				self.print(f"  User: {command_data['user']}s")
			if command_data.get('notification'):
				notification_str = {
					True: 'On',
					False: 'Off',
					None: 'Inherit'
				}[command_data['notification']]
				self.print(f"  Notification Override: {notification_str}")

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
