from base.module import ModuleBase, ModuleAdminCommand
from base.events import EVT_HOST, EVT_RAID, ChatCommandEvent

import re

class RaidHost(ModuleBase):
	module_name = "raid_host"
	def setup(self):
		self._module_data = self.get_module_data()
		if not 'attachments' in self._module_data:
			self._module_data['attachments'] = {}

		self.register_admin_command(ModuleAdminCommand(
			'attach_raid',
			self._attach_raid,
			usage = f'{self.module_name} attach_raid <!command/none>',
			description = 'Run !<command> when a user raids the channel. Set to "none" to remove',
		))

		self.register_admin_command(ModuleAdminCommand(
			'attach_host',
			self._attach_host,
			usage = f'{self.module_name} attach_host <!command/none>',
			description = 'Run !<command> when a user hosts the channel. Set to "none" to remove',
		))

		self.event_listen(EVT_RAID, self.raid)
		self.event_listen(EVT_HOST, self.host)

	def raid(self, event):
		message = f"Just raided by {event.display_name} with {event.viewer_count} viewers!"
		self.print(message)

		command_str = self._module_data['attachments'].get('raid')
		if command_str is not None:
			command_event = ChatCommandEvent(
				command_str,
				"",
				event.display_name,
				event.user_id,
				False,
				False,
				False,
				bypass_permissions = True,
				viewer_count = event.viewer_count
			)
			self.event_loop.event_queue.put(command_event)

	def host(self, event):
		message = f"Just hosted by {event.display_name}!"
		self.print(message)

		command_str = self._module_data['attachments'].get('host')
		if command_str is not None:
			command_event = ChatCommandEvent(
				command_str,
				"",
				event.display_name,
				event.user_id,
				False,
				False,
				False,
				bypass_permissions = True
			)
			self.event_loop.event_queue.put(command_event)

	def _attach_raid(self, input, command):
		self._attach('raid', input, command)

	def _attach_host(self, input, command):
		self._attach('host', input, command)

	def _attach(self, key, input, command):
		if input.lower().strip() == 'none':
			self._module_data['attachments'][key] = None
			self.print('Attachment removed')
			return
		match = re.search(r'^!([^ ]+)$', input)
		if not match:
			self.print(f'Usage: {command.usage}')
			current = self._module_data['attachments'].get(key)
			if current:
				self.print(f'Currently set to !{current}')
			else:
				self.print('Not currently set')
			return

		command = match.group(1).lower()

		self._module_data['attachments'][key] = command
		self.save_module_data(self._module_data)
		self.print(f'{key.capitalize()}s now attached to !{command}')

	def shutdown(self):
		self.save_module_data(self._module_data)
