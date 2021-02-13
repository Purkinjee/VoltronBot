from base.module import ModuleBase, ModuleAdminCommand
from base.events import EVT_TIMER, EVT_CHATCOMMAND
import time
import re

class Timer(ModuleBase):
	module_name = 'timer'
	def setup(self):
		## Do not allow timers greater than 25 hours
		self.max_timer_len = 25 * 60
		self._timer_data = self.get_module_data()

		## Create empty list of timers if this is the first
		## time the module has been loaded
		if not 'timers' in self._timer_data:
			self._timer_data['timers'] = []

		self.register_admin_command(ModuleAdminCommand(
			'list',
			self._list_timers,
			usage = f'{self.module_name} list',
			description = 'List all active timers'
		))

		self.register_admin_command(ModuleAdminCommand(
			'clear',
			self._clear_timers,
			usage = f'{self.module_name} clear',
			description = 'Clear all timers'
		))

		self.event_listen(EVT_CHATCOMMAND, self.command)
		self.event_listen(EVT_TIMER, self.timer_check)

	def command(self, event):
		if event.command != 'timer':
			return False

		match = re.search(r'^(add )?([\d]+) ?(.+)?$', event.message)
		if not match:
			return False


		minutes = int(match.group(2))
		## Do not allow timers to be set if minutes > max_timer_len
		if minutes > self.max_timer_len:
			self.send_chat_message(f"@{event.display_name} please don't set ridiculous timers.")
			return True
		message = match.group(3)

		## Adding time to a timer requires a timer with a matching message
		if match.group(1) and not message:
			self.send_chat_message(f"@{event.display_name} you can only add to a named timer.")
			return True

		## If we are adding time to a timer
		if match.group(1):
			timer = None
			for timer in self._timer_data['timers']:
				if timer[1] == message:
					## We found a match!
					break
			if not timer:
				## We didnt' find a match
				self.send_chat_message(f'@{event.display_name} No active timers named "{message}"')
				return True

			## Add time to the existing timer, create a new entry
			## and delete the old one
			new_time = timer[0] + (minutes * 60)
			self._timer_data['timers'].remove(timer)
			self._timer_data['timers'].append((new_time, message))
			minutes = int((new_time - time.time()) / 60)
			self.send_chat_message(f"@{event.display_name} timer increased to {minutes} minutes")
			return True

		if not message:
			message = "Timer Expired!"

		exp_time = time.time() + (minutes * 60)

		self._timer_data['timers'].append((exp_time, message))
		self.save_module_data(self._timer_data)

		self.send_chat_message(f'@{event.display_name} timer set for {minutes} minute(s)')
		return True

	def _list_timers(self, input, command):
		if not self._timer_data['timers']:
			self.buffer_print('VOLTRON', 'No timers set')
			return

		for timer in self._timer_data['timers']:
			expire_time = time.localtime(timer[0])
			expire_time_str = time.strftime("%Y-%m-%d %H:%M", expire_time)
			self.buffer_print('VOLTRON', f"{expire_time_str}: {timer[1]}")

	def _clear_timers(self, input, command):
		def confirm(prompt):
			if prompt.lower() == 'y':
				self._timer_data['timers'] = []
				self.save_module_data(self._timer_data)
				self.buffer_print('VOLTRON', 'Timers cleared.')
				self.update_status_text()
				return True
			if prompt.lower() == 'n':
				self.update_status_text()
				return True
			else:
				return False

		self.update_status_text('Are you sure you want to clear all active timers?')
		self.prompt_ident = self.get_prompt('[Y]es/[N]o > ', confirm)

	def timer_check(self, event):
		to_remove = []
		for timer in self._timer_data['timers']:
			## In case old timers are hanging around with ridiculous times
			## In older version of voltron there wasn't a limit and insanely long
			## timers were gettings set. Clean them up here!
			if (timer[0] - time.time()) > self.max_timer_len*60:
				to_remove.append(timer)
			## Check if it's time to send a message
			if time.time() > timer[0]:
				self.send_chat_message(timer[1])
				## Can't modify the list while iterating through it.
				## do it later
				to_remove.append(timer)

		## Remove all timers that have elapsed
		for remove in to_remove:
			self._timer_data['timers'].remove(remove)

		## Only hit the db if we modified stuff
		if to_remove:
			self.save_module_data(self._timer_data)


	def shutdown(self):
		self.save_module_data(self._timer_data)
