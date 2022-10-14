from base.module import ModuleBase, ModuleAdminCommand
from base.events import EVT_TIMER, EVT_CHATMESSAGE
import time

class Rotator(ModuleBase):
	module_name = "rotator"
	_default_time_threshold = 600 ## 10 minutes
	_default_message_threshold = 20
	def setup(self):
		self._rotator_data = self.get_module_data()
		self._last_time = time.time()
		self._message_count = 0
		self._message_index = 0
		self.prompt_ident = None

		self.register_admin_command(ModuleAdminCommand(
			'add',
			self.add_message,
			usage = f'{self.module_name} add <message>',
			description = 'Add a message for the rotator',
		))

		self.register_admin_command(ModuleAdminCommand(
			'pause',
			self.pause_message,
			usage = f'{self.module_name} pause',
			description = 'Pause or resume a specific rotator message',
		))

		self.register_admin_command(ModuleAdminCommand(
			'delete',
			self.delete_message,
			usage = f'{self.module_name} delete',
			description = 'Delete an existing message in the rotator',
		))

		self.register_admin_command(ModuleAdminCommand(
			'list',
			self.list_messages,
			usage = f'{self.module_name} list',
			description = 'List messages to rotate',
		))

		self.register_admin_command(ModuleAdminCommand(
			'time',
			self.set_time_threshold,
			usage = f'{self.module_name} time <minutes>',
			description = 'Set time threshold between sending messages',
		))

		self.register_admin_command(ModuleAdminCommand(
			'messagecount',
			self.set_message_threshold,
			usage = f'{self.module_name} messagecount <messages>',
			description = 'Set how many chat messages must occur bettween events',
		))

		self.register_admin_command(ModuleAdminCommand(
			'announce',
			self.set_announce,
			usage = f'{self.module_name} announce <on/off>',
			description = 'If enabled will use /announce for rotator messages.',
		))

		self.event_listen(EVT_TIMER, self.timer)
		self.event_listen(EVT_CHATMESSAGE, self.chat_message)

	def timer(self, event):
		messages = self._rotator_data.get('messages', [])
		if not messages:
			return

		paused = self._rotator_data.get('paused', [])

		elapsed = time.time() - self._last_time

		if elapsed >= self.time_threshold and self._message_count >= self.message_threshold:
			message_index = self._next_index()
			if message_index is None:
				return

			message = messages[message_index]
			if self._rotator_data.get('announce', False):
				message = f'/announce {message}'
			self.send_chat_message(message)
			self._message_count = 0
			self._last_time = time.time()

	def _are_all_paused(self):
		messages = self._rotator_data.get('messages', [])
		paused = self._rotator_data.get('paused', [])
		all_paused = True

		message_count = len(messages)
		index = 0
		while index < (message_count):
			if not index in paused:
				all_paused = False
				break
			index += 1

		return all_paused

	def _next_index(self):
		messages = self._rotator_data.get('messages', [])
		paused = self._rotator_data.get('paused', [])

		if not messages:
			return None

		if self._are_all_paused():
			return None

		if len(messages) <= self._message_index:
			self._message_index = 0

		while self._message_index in paused:
			self._message_index += 1
			if len(messages) <= self._message_index:
				self._message_index = 0

		this_index = self._message_index
		self._message_index += 1
		return this_index


	def chat_message(self, event):
		self._message_count += 1

	def add_message(self, input, command):
		if not input:
			self.print(f'Usage: {command.usage}')
			return

		if not 'messages' in self._rotator_data:
			self._rotator_data['messages'] = []

		self._rotator_data['messages'].append(input)
		self.save_module_data(self._rotator_data)

		self.print(f"Rotator message added: {input}")

	def pause_message(self, input, command):
		message_list = self.list_messages()

		def select_message(prompt):
			if prompt.lower().strip() == 'c':
				self.update_status_text()
				return True

			if not prompt.isdigit():
				return False

			selection = int(prompt)

			if selection < 0 or selection > len(message_list):
				self.print('Invalid selection')
				return False

			selection = selection - 1
			selected_message = message_list[selection]

			paused = self._rotator_data.get('paused', [])
			if selection in paused:
				self.print(f'Message Resumed: {selected_message}')
				paused.remove(selection)
			else:
				self.print(f'Message Paused: {selected_message}')
				paused.append(selection)

			self._rotator_data['paused'] = paused
			self.save_module_data(self._rotator_data)
			self.update_status_text()
			return True

		self.update_status_text('Select message to pause/resume, c to cancel')
		self.prompt_ident = self.get_prompt('Message Number> ', select_message)

	def list_messages(self, input=None, command=None):
		messages = self._rotator_data.get('messages', [])

		if not messages:
			self.print('No rotator messages set')
			return

		paused = self._rotator_data.get('paused', [])

		self.print('Rotator messages:')
		counter = 1
		for message in messages:
			if (counter-1) in paused:
				self.print(f'  {counter}. {message} [PAUSED]')
			else:
				self.print(f'  {counter}. {message}')
			counter += 1

		return messages

	def delete_message(self, input, command):
		message_list = self.list_messages()

		def select_message(prompt):
			if prompt.lower().strip() == 'c':
				self.update_status_text()
				return True

			if not prompt.isdigit():
				return False

			selection = int(prompt)

			if selection < 0 or selection > len(message_list):
				self.print('Invalid selection')
				return False

			selected_message = message_list[selection-1]

			def confirm(prompt):
				prompt = prompt.lower().strip()
				if prompt == 'n':
					self.update_status_text()
					return True
				if prompt != 'y':
					return False

				self._rotator_data['messages'].remove(selected_message)
				self.save_module_data(self._rotator_data)
				self.print('Message deleted.')
				self.update_status_text()
				return True

			self.print('Selected Message:')
			self.print(selected_message)
			self.update_status_text('Delete message?')
			self.terminate_prompt(self.prompt_ident)
			self.prompt_ident = self.get_prompt('[Y]es/[N]o> ', confirm)

		self.update_status_text('Select message to delete, c to cancel')
		self.prompt_ident = self.get_prompt('Message Number> ', select_message)

	def set_time_threshold(self, input, command):
		if not input.isdigit():
			self.print(f'Usage: {command.usage}')
			self.print(f'Current time: {int(self.time_threshold/60)}m')
			return

		new_time = int(input)

		self._rotator_data['time_threshold'] = new_time * 60
		self.save_module_data(self._rotator_data)
		self.print(f'Time interval set to {new_time} minutes')

	def set_message_threshold(self, input, command):
		if not input.isdigit():
			self.print(f'Usage: {command.usage}')
			self.print(f'Current message count: {self.message_threshold}')
			return

		new_threshold = int(input)

		self._rotator_data['message_threshold'] = new_threshold
		self.save_module_data(self._rotator_data)
		self.print(f'Message count set to {new_threshold}')

	def set_announce(self, input, command):
		input = input.lower().strip()

		if input == 'on':
			self._rotator_data['announce'] = True
			self.print('Announce mode enabled')
		elif input == 'off':
			self._rotator_data['announce'] = False
			self.print('Announce mode disabled')

		self.save_module_data(self._rotator_data)

	def shutdown(self):
		self.save_module_data(self._rotator_data)

	@property
	def time_threshold(self):
		return self._rotator_data.get('time_threshold', self._default_time_threshold)

	@property
	def message_threshold(self):
		return self._rotator_data.get('message_threshold', self._default_message_threshold)
