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

		self.event_listen(EVT_CHATCOMMAND, self.command)
		self.event_listen(EVT_TIMER, self.timer_check)

	def command(self, event):
		match = re.search(r'^([\d]+) ?(.+)?$', event.message)
		if not match:
			return False

		minutes = int(match.group(1))
		message = match.group(2)

		if not message:
			message = "Timer Expired!"

		exp_time = time.time() + (minutes * 60)

		self._timer_data['timers'].append((exp_time, message))
		self.save_module_data(self._timer_data)

		self.send_chat_message(f'@{event.display_name} timer set for {minutes} minute(s)')

		return True

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


	def shutdown(self):
		self.save_module_data(self._timer_data)
