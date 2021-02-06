from base.module import ModuleBase, ModuleAdminCommand
from base.events import EVT_BITS, ChatCommandEvent

import re

class BitsModule(ModuleBase):
	module_name = 'bits'
	def setup(self):
		self._module_data = self.get_module_data()
		if not 'attachments' in self._module_data:
			self._module_data['attachments'] = {}

		self.register_admin_command(ModuleAdminCommand(
			'attach',
			self._attach_bits,
			usage = f'{self.module_name} attach <!command/none>',
			description = 'Run !<command> when a user cheers bits in the channel. Set to "none" to remove',
		))

		self.event_listen(EVT_BITS, self.bits)

	def bits(self, event):
		message = None
		if event.is_anonymous:
			message = f"An anonymous viewer cheered {event.bits_used} bits!"
		else:
			message = f"{event.display_name} just cheered {event.bits_used} bits!"

		if message is not None:
			self.buffer_print('VOLTRON', message)

		command = self._module_data['attachments'].get('cheer')
		if not command:
			return

		command_event = ChatCommandEvent(
			command,
			event.message,
			event.display_name,
			event.user_id,
			False,
			False,
			False,
			bypass_permissions = True,
			bits_used = event.bits_used,
			total_bits_used = event.total_bits_used
		)
		self.event_loop.event_queue.put(command_event)

	def _attach_bits(self, input, command):
		if input.lower().strip() == 'none':
			self._module_data['attachments']['cheer'] = None
			self.buffer_print('VOLTRON', 'Attachment removed')
			return
		match = re.search(r'^!([^ ]+)$', input)
		if not match:
			self.buffer_print('VOLTRON', f'Usage: {command.usage}')
			current = self._module_data['attachments'].get('cheer')
			if current:
				self.buffer_print('VOLTRON', f'Currently set to !{current}')
			else:
				self.buffer_print('VOLTRON', 'Not currently set')
			return

		command = match.group(1).lower()

		self._module_data['attachments']['cheer'] = command
		self.save_module_data(self._module_data)
		self.buffer_print('VOLTRON', f'Bits now attached to !{command}')

	def shutdown(self):
		self.save_module_data(self._module_data)
