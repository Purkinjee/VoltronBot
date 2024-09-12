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
			usage = f'{self.module_name} attach <!command/none> <tier>',
			description = 'Run !<command> when a user subs to the channel. Set to "none" to remove. Tier is optional.',
		))

		self.register_admin_command(ModuleAdminCommand(
			'attach_gift',
			self._attach_gift,
			usage = f'{self.module_name} attach_gift !<command> <tier>',
			description = 'Run !<command> when a user gifts a sub to the channel. Set to "none" to remove. Tier is optional.',
		))

		self.register_admin_command(ModuleAdminCommand(
			'list',
			self._list,
			usage = f'{self.module_name} list',
			description = 'List sub attachments',
		))

		self.event_listen(EVT_SUBSCRIPTION, self.subscription)

	def subscription(self, event):
		message = None
		if event.is_anonymous:
			message = f"Anonymous sub ({event.sub_tier_name}) was gifted to {event.recipient_display_name}"
		elif event.is_gift:
			message = f"{event.display_name} gifted a {event.duration} month {event.sub_tier_name} sub to {event.recipient_display_name}"
		else:
			message = f"{event.display_name} just subscribed! ({event.sub_tier_name}, {event.cumulative_months} months)"

		if message is not None:
			self.print(message)

		if event.is_gift:
			command = self._module_data['attachments'].get('gift')
			tier_command = self._module_data['attachments'].get(f'gift{event.sub_tier}')
			if tier_command is not None:
				command = tier_command

			if command:
				## First item in the command str is the command name
				## followed by args. If there are no args pass the message
				## from the event.
				command_args = command.split()
				message = ' '.join(command_args[1:])
				#if not message:
				#	message = event.message
				command_event = ChatCommandEvent(
					command_args[0],
					message,
					event.display_name,
					event.user_id,
					False,
					False,
					False,
					bypass_permissions = True,
					msg_id= None,
					context = event.context,
					sub_plan = event.sub_plan,
					sub_plan_name = event.sub_plan_name,
					cumulative_months = event.cumulative_months,
					streak_months = event.streak_months,
					recipient_display_name = event.recipient_display_name,
					recipient_id = event.recipient_id,
					duration = event.duration,
					sub_tier_name = event.sub_tier_name

				)
				self.event_loop.event_queue.put(command_event)
		else:
			command = self._module_data['attachments'].get('sub')
			tier_command = self._module_data['attachments'].get(f'sub{event.sub_tier}')
			if tier_command is not None:
				command = tier_command
			if command:
				## First item in the command str is the command name
				## followed by args. If there are no args pass the message
				## from the event.
				command_args = command.split()
				message = ' '.join(command_args[1:])
				#if not message:
				#	message = event.message
				command_event = ChatCommandEvent(
					command_args[0],
					message,
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
					streak_months = event.streak_months,
					sub_message = event.message,
					sub_tier_name = event.sub_tier_name,
					duration = 1,
					msg_id= None
				)
				self.event_loop.event_queue.put(command_event)

	def _attach_sub(self, input, command):
		## !command or none followed by 1, 2, or 3
		match = re.search(r'^(!([^ ]+.*?)|none)((\s+([1-3])$)|$)', input)
		if not match:
			self.print(f'Usage: {command.usage}')
			return

		command = match.group(1)
		tier = match.group(5)
		key = 'sub'
		if tier is not None:
			key += str(tier)

		if command == 'none':
			self._module_data['attachments'][key] = None
			if tier is None:
				self.print('Sub (No Tier) attachment removed')
			else:
				self.print(f'Sub (Tier {tier}) attachment removed')
			return
		else:
			command = match.group(2)

		self._module_data['attachments'][key] = command
		self.save_module_data(self._module_data)
		tier_str = "No Tier"
		if tier:
			tier_str = f'Tier {tier}'
		self.print(f'Subscriptions ({tier_str}) now attached to !{command}')

	def _attach_gift(self, input, command):
		## !command or none followed by 1, 2, or 3
		match = re.search(r'^(!([^ ]+.*?)|none)((\s+([1-3])$)|$)', input)
		if not match:
			self.print(f'Usage: {command.usage}')
			return

		command = match.group(1)
		tier = match.group(5)
		key = 'gift'
		if tier is not None:
			key += str(tier)

		if command == 'none':
			self._module_data['attachments'][key] = None
			if tier is None:
				self.print('Sub (No Tier) attachment removed')
			else:
				self.print(f'Sub (Tier {tier}) attachment removed')
			return
		else:
			command = match.group(2)

		self._module_data['attachments'][key] = command
		self.save_module_data(self._module_data)
		tier_str = "No Tier"
		if tier:
			tier_str = f'Tier {tier}'
		self.print(f'Gift Subscriptions ({tier_str}) now attached to !{command}')

	def _list(self, input, commmand):
		key_map = {
			'sub': 'Sub (Any Tier)',
			'sub1': 'Sub (Tier 1)',
			'sub2': 'Sub (Tier 2)',
			'sub3': 'Sub (Tier 3)',
			'gift': 'Gift Sub (Any Tier)',
			'gift1': 'Gift Sub (Tier 1)',
			'gift2': 'Gift Sub (Tier 2)',
			'gift3': 'Gift Sub (Tier 3)'
		}

		self.print('Sub Attachments:')
		for key in ('sub', 'sub1', 'sub2', 'sub3', 'gift', 'gift1', 'gift2', 'gift3'):
			command = self._module_data['attachments'].get(key)
			if command is None:
				command = 'Not Set'
			else:
				command = f'!{command}'

			self.print(f"  {key_map[key]}: {command}")


	def shutdown(self):
		self.save_module_data(self._module_data)
