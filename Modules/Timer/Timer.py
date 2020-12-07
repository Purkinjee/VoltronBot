from base.module import ModuleBase, ModuleAdminCommand
from base.events import EVT_TIMER, EVT_CHATCOMMAND
import time
import re

class Timer(ModuleBase):
	module_name = 'timer'
	def setup(self):
		self._timer_data = self.get_module_data()
		if not 'timers' in self._timer_data:
			self._timer_data['timers'] = []

		self.register_admin_command(ModuleAdminCommand(
			'permission',
			self._set_permission,
			usage = f'{self.module_name} permission <all/mod/brodcaster>',
			description = 'Set permission for timer use in chat'
		))

		self.event_listen(EVT_CHATCOMMAND, self.command)
		self.event_listen(EVT_TIMER, self.timer_check)

	def command(self, event):
		if event.command != 'timer':
			return

		if self.broadcaster_only and not event.is_broadcaster:
			return

		if self.mod_only and not event.is_mod:
			return

		match = re.search(r'^([\d]+) ?(.+)?$', event.args)
		if not match:
			return

		minutes = int(match.group(1))
		message = match.group(2)

		if not message:
			message = "Timer Expired!"

		exp_time = time.time() + (minutes * 60)

		self._timer_data['timers'].append((exp_time, message))
		self.save_module_data(self._timer_data)

		self.send_chat_message(f'@{event.display_name} timer set for {minutes} minute(s)')

	def timer_check(self, event):
		to_remove = []
		for timer in self._timer_data['timers']:
			if time.time() > timer[0]:
				self.send_chat_message(timer[1])
				to_remove.append(timer)

		for remove in to_remove:
			self._timer_data['timers'].remove(remove)

		if to_remove:
			self.save_module_data(self._timer_data)

	def _set_permission(self, input, command):
		if input.lower().strip() not in ['all', 'mod', 'broadcaster']:
			current_permission = self._timer_data.get('permission', 'all')
			self.buffer_print('VOLTRON', f'Usage: {command.usage}')
			self.buffer_print('VOLTRON', f'Current permission: {current_permission}')
			return

		self._timer_data['permission'] = input.lower().strip()
		self.save_module_data(self._timer_data)

		self.buffer_print('VOLTRON', f'Timer permission set to {input.lower().strip()}')

	def shutdown(self):
		self.save_module_data(self._timer_data)

	@property
	def mod_only(self):
		permission = self._timer_data.get('permission', 'all')
		if permission == 'mod':
			return True

		return False

	@property
	def broadcaster_only(self):
		permission = self._timer_data.get('permission', 'all')
		if permission == 'broadcaster':
			return True

		return False
