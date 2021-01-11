from base.module import ModuleBase, ModuleAdminCommand
from base.events import EVT_POINT_REDEMPTION, ChatCommandEvent
import re

from lib.common import get_broadcaster

class ChannelPointModule(ModuleBase):
	module_name = "channel_points"
	def setup(self):
		self._channel_point_data = self.get_module_data()
		if not 'attachments' in self._channel_point_data:
			self._channel_point_data['attachments'] = {}

		self.register_admin_command(ModuleAdminCommand(
			'attach',
			self._attach_reward,
			usage = f'{self.module_name} attach',
			description = 'Attach a reward redemption to a command',
		))

		self.register_admin_command(ModuleAdminCommand(
			'list',
			self._list_rewards,
			usage = f'{self.module_name} list',
			description = 'List all configured rewards',
		))

		self.register_admin_command(ModuleAdminCommand(
			'delete',
			self._delete_reward,
			usage = f'{self.module_name} delete',
			description = 'Delete a reward redemption',
		))

		self.event_listen(EVT_POINT_REDEMPTION, self.points_redeemed)

	def points_redeemed(self, event):
		if not event.reward_id in self._channel_point_data['attachments']:
			return

		command = self._channel_point_data['attachments'][event.reward_id].get('command')
		if command:
			command_event = ChatCommandEvent(
				command,
				event.user_input,
				event.display_name,
				event.user_id,
				False,
				False,
				bypass_permissions = True
			)
			self.event_loop.event_queue.put(command_event)

	def _attach_reward(self, input, command):
		b = get_broadcaster()
		rewards = b.twitch_api.get_rewards(b.twitch_user_id)
		if not rewards:
			self.buffer_print('VOLTRON', 'No rewards set up or unable to retrive from Twitch')
			return

		rewards_list = [(x['id'], x['title']) for x in rewards]
		index = 1
		for r in rewards_list:
			self.buffer_print('VOLTRON', f"{index}. {r[1]}")
			index += 1

		def select_reward(prompt):
			if prompt == 'c':
				self.update_status_text()
				return True

			elif not prompt.isdigit():
				return False

			index = int(prompt)
			if len(rewards_list) < index or index < 0:
				self.buffer_print('VOLTRON', 'Invalid Selection')
				return False

			selected_reward = rewards_list[index-1]

			def command_selected(prompt):
				if prompt == 'c':
					self.update_status_text()
					return True
				match = re.search(r'^!([^ ]+)$', prompt)
				if not match:
					self.buffer_print('VOLTRON', 'Please type a valid command beginning with !')
					return False

				command = match.group(1)
				reward_data = self._channel_point_data['attachments'].get(selected_reward[0], {})
				reward_data['command'] = command

				self._channel_point_data['attachments'][selected_reward[0]] = reward_data
				self.save_module_data(self._channel_point_data)

				self.buffer_print('VOLTRON', f"{selected_reward[1]} is now attached to !{command}")
				self.update_status_text()
				return True

			self.update_status_text(f'Type !<command> to attach to {selected_reward[1]}. c to cancel.')
			self.get_prompt('Command > ', command_selected)
			return True


		self.update_status_text('Select reward to attach. c to cancel.')
		self.prompt_ident = self.get_prompt('Reward #> ', select_reward)

	def _list_rewards(self, input, command):
		if not self._channel_point_data['attachments']:
			self.buffer_print('VOLTRON', 'No channel point redemptions configured')
			return

		b = get_broadcaster()
		rewards = b.twitch_api.get_rewards(b.twitch_user_id)

		reward_map = {x['id']:x['title'] for x in rewards}

		self.buffer_print('VOLTRON', 'Attached channel point redemptions:')

		for reward_id in self._channel_point_data['attachments']:
			self.buffer_print('VOLTRON', f"  {reward_map.get(reward_id, '<deleted>')} - !{self._channel_point_data['attachments'][reward_id].get('command')}")

	def _delete_reward(self, input, command):
		if not self._channel_point_data['attachments']:
			self.buffer_print('VOLTRON', 'No channel point redemptions configured')
			return

		b = get_broadcaster()
		rewards = b.twitch_api.get_rewards(b.twitch_user_id)

		reward_map = {x['id']:x['title'] for x in rewards}

		self.buffer_print('VOLTRON', 'Select reward to delete:')
		selection_map = {}
		count = 1
		for reward_id in self._channel_point_data['attachments']:
			command = self._channel_point_data['attachments'][reward_id].get('command')
			self.buffer_print('VOLTRON', f"{count}. {reward_map.get(reward_id, '<deleted>')} - !{command}")
			selection_map[count] = reward_id
			count += 1

		def select_reward(input):
			if input.lower() == 'c':
				self.update_status_text()
				return True

			if not input.isdigit():
				return False

			selection = int(input)
			reward_id = selection_map.get(selection)
			if not reward_id:
				self.buffer_print('VOLTRON', f'Invalid Selection: {input}')

			def confirm(input):
				command = input.lower().strip()
				if command == 'n':
					self.update_status_text()
					return True
				if command == 'y':
					del self._channel_point_data['attachments'][reward_id]
					self.save_module_data(self._channel_point_data)
					self.buffer_print('VOLTRON', f"{reward_map.get(reward_id, '<deleted>')} successfully deleted")
					self.update_status_text()
					return True

			self.update_status_text(f"Delete {reward_map.get(reward_id, '<deleted>')}?")
			self.terminate_prompt(self.prompt_ident)
			self.prompt_ident = self.get_prompt('Y/N > ', confirm)

		self.update_status_text('Select channel point redemption to delete. c to cancel')
		self.prompt_ident = self.get_prompt('Reward #> ', select_reward)

	def shutdown(self):
		self.save_module_data(self._channel_point_data)
