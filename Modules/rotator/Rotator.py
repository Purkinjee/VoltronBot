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

		self.event_listen(EVT_TIMER, self.timer)
		self.event_listen(EVT_CHATMESSAGE, self.chat_message)

	def timer(self, event):
		messages = self._rotator_data.get('messages', [])
		if not messages:
			return

		elapsed = time.time() - self._last_time

		if elapsed >= self.time_threshold and self._message_count >= self.message_threshold:
			if len(messages) <= self._message_index:
				self._message_index = 0
			self.send_chat_message(messages[self._message_index])
			self._message_count = 0
			self._last_time = time.time()
			self._message_index += 1

	def chat_message(self, event):
		self._message_count += 1

	def add_message(self, input, command):
		if not input:
			self.buffer_print('VOLTRON', f'Usage: {command.usage}')
			return

		if not 'messages' in self._rotator_data:
			self._rotator_data['messages'] = []

		self._rotator_data['messages'].append(input)
		self.save_module_data(self._rotator_data)

		self.buffer_print('VOLTRON', f"Rotator message added: {input}")

	def list_messages(self, input, command):
		messages = self._rotator_data.get('messages', [])

		if not messages:
			self.buffer_print('VOLTRON', 'No rotator messages set')
			return

		self.buffer_print('VOLTRON', 'Rotator messages:')
		counter = 1
		for message in messages:
			self.buffer_print('VOLTRON', f'  {counter}. {message}')
			counter += 1

		return messages

	def delete_message(self, input, command):
		message_list = self.list_messages(None)

		def select_message(prompt):
			if prompt.lower().strip() == 'c':
				self.update_status_text()
				return True

			if not prompt.isdigit():
				return False

			selection = int(prompt)

			if selection < 0 or selection > len(message_list):
				self.buffer_print('VOLTRON', 'Invalid selection')
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
				self.buffer_print('VOLTRON', 'Message deleted.')
				self.update_status_text()
				return True

			self.buffer_print('VOLTRON', 'Selected Message:')
			self.buffer_print('VOLTRON', selected_message)
			self.update_status_text('Delete message?')
			self.terminate_prompt(self.prompt_ident)
			self.prompt_ident = self.get_prompt('[Y]es/[N]o> ', confirm)

		self.update_status_text('Select message to delete, c to cancel')
		self.prompt_ident = self.get_prompt('Message Number> ', select_message)

	def set_time_threshold(self, input, command):
		if not input.isdigit():
			self.buffer_print('VOLTRON', f'Usage: {command.usage}')
			self.buffer_print('VOLTRON', f'Current time: {int(self.time_threshold/60)}m')
			return

		new_time = int(input)

		self._rotator_data['time_threshold'] = new_time * 60
		self.save_module_data(self._rotator_data)
		self.buffer_print('VOLTRON', f'Time interval set to {new_time} minutes')

	def set_message_threshold(self, input, command):
		if not input.isdigit():
			self.buffer_print('VOLTRON', f'Usage: {command.usage}')
			self.buffer_print('VOLTRON', f'Current message count: {self.message_threshold}')
			return

		new_threshold = int(input)

		self._rotator_data['message_threshold'] = new_threshold
		self.save_module_data(self._rotator_data)
		self.buffer_print('VOLTRON', f'Message count set to {new_threshold}')

	def shutdown(self):
		self.save_module_data(self._rotator_data)

	@property
	def time_threshold(self):
		return self._rotator_data.get('time_threshold', self._default_time_threshold)

	@property
	def message_threshold(self):
		return self._rotator_data.get('message_threshold', self._default_message_threshold)
