from base.module import ModuleBase, ModuleAdminCommand
from base.events import EVT_SUBSCRIPTION, ChatCommandEvent

import re

class SubModule(ModuleBase):
	module_name = "subs"
	def setup(self):
		self._module_data = self.get_module_data()
		if not 'attachments' in self._module_data:
			self._module_data['attachments'] = {}

		self.register_admin_command(ModuleAdminCommand(
			'attach',
			self._attach_sub,
			usage = f'{self.module_name} attach !<command>',
			description = 'Run !<command> when a user subs to the channel. Set to "none" to remove',
		))

		self.register_admin_command(ModuleAdminCommand(
			'attach_gift',
			self._attach_gift,
			usage = f'{self.module_name} attach_gift !<command>',
			description = 'Run !<command> when a user gifts a sub to the channel. Set to "none" to remove.',
		))

		self.event_listen(EVT_SUBSCRIPTION, self.subscription)

	def subscription(self, event):
		if event.is_gift:
			command = self._module_data['attachments'].get('gift')
			command_event = ChatCommandEvent(
				command,
				event.recipient_display_name,
				event.display_name,
				event.user_id,
				False,
				False,
				False,
				bypass_permissions = True,
				context = event.context,
				sub_plan = event.sub_plan,
				sub_plan_name = event.sub_plan_name,
				cumulative_months = event.cumulative_months,
				stream_months = event.streak_months,
				recipient_display_name = event.recipient_display_name,
				recipient_id = event.recipient_id,
				duration = event.duration
			)
			self.event_loop.event_queue.put(command_event)
		else:
			command = self._module_data['attachments'].get('sub')
			to_include = ('context', 'sub_plan', 'sub_plan_name', )
			if command:
				command_event = ChatCommandEvent(
					command,
					event.message,
					event.display_name,
					event.user_id,
					False,
					False,
					False,
					bypass_permissions = True,
					context = event.context,
					sub_plan = event.sub_plan,
					sub_plan_name = event.sub_plan_name,
					cumulative_months = event.cumulative_months,
					stream_months = event.streak_months
				)
				self.event_loop.event_queue.put(command_event)

	def _attach_sub(self, input, command):
		if input.lower().strip() == 'none':
			self._module_data['attachments']['sub'] = None
			self.buffer_print('VOLTRON', 'Sub attachment removed')
			return
		match = re.search(r'^!([^ ]+)$', input)
		if not match:
			self.buffer_print('VOLTRON', f'Usage: {command.usage}')
			current = self._module_data['attachments'].get('sub')
			if current:
				self.buffer_print('VOLTRON', f'Currently set to !{current}')
			else:
				self.buffer_print('VOLTRON', 'Not currently set')
			return

		command = match.group(1).lower()

		self._module_data['attachments']['sub'] = command
		self.save_module_data(self._module_data)
		self.buffer_print('VOLTRON', f'Subscriptions now attached to !{command}')

	def _attach_gift(self, input, command):
		if input.lower().strip() == 'none':
			self._module_data['attachments']['gift'] = None
			self.buffer_print('VOLTRON', 'Gift sub attachment removed')
			return
		match = re.search(r'^!([^ ]+)$', input)
		if not match:
			self.buffer_print('VOLTRON', f'Usage: {command.usage}')
			current = self._module_data['attachments'].get('gift')
			if current:
				self.buffer_print('VOLTRON', f'Currently set to !{current}')
			else:
				self.buffer_print('VOLTRON', 'Not currently set')
			return

		command = match.group(1).lower()

		self._module_data['attachments']['gift'] = command
		self.save_module_data(self._module_data)
		self.buffer_print('VOLTRON', f'Gift subscriptions now attached to !{command}')


	def shutdown(self):
		self.save_module_data(self._module_data)
