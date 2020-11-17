import re
import os

from base.module import ModuleBase, ModuleAdminCommand
from lib.common import get_broadcaster
from base.events import EVT_FIRST_MESSAGE, EVT_CHATCOMMAND

class EntranceSounds(ModuleBase):
	module_name = "entrance_sounds"
	def setup(self):
		if not os.path.isdir(self.media_directory):
			os.makedirs(self.media_directory)

		self._sound_data = self.get_module_data()
		self._sound_command = self._sound_data.get('sound_command', 'hi')
		if not 'user_sounds' in self._sound_data.keys():
			self._sound_data['user_sounds'] = {}


		self.register_admin_command(ModuleAdminCommand(
			'command',
			self._set_command,
			usage = f'{self.module_name} command !<command>',
			description = 'Set command for users to play their entrance sound'
		))

		self.register_admin_command(ModuleAdminCommand(
			'add',
			self._add_entrance_sound,
			usage = f'{self.module_name} add <twitch_user> <sound.mp3>',
			description = 'Add entrance sound for <twitch_user>'
		))

		self.register_admin_command(ModuleAdminCommand(
			'remove',
			self._remove_entrance_sound,
			usage = f'{self.module_name} remove <twitch_user>',
			description = 'Remove entrance sound for <twitch_user>'
		))

		self.register_admin_command(ModuleAdminCommand(
			'list',
			self._list_entrance_sounds,
			usage = f'{self.module_name} list',
			description = 'List entrance sounds'
		))

		self.event_listen(EVT_FIRST_MESSAGE, self.first_message)
		self.event_listen(EVT_CHATCOMMAND, self.command)

	def first_message(self, event):
		if event.user_id in self._sound_data['user_sounds']:
			data = self._sound_data['user_sounds'][event.user_id]

			sound_path = f"{self.media_directory}\\{data['sound_file']}"
			if not os.path.isfile(sound_path):
				self.buffer_print('ERR', f'{sound_path} does not exist')
				return

			self.play_audio(sound_path)

	def command(self, event):
		if event.command != self._sound_command:
			return

		self.first_message(event)

	def _set_command(self, input, command):
		match = re.search(r'^!([^ ]+)$', input)

		if not match:
			self.buffer_print('VOLTRON', f'Usage: {command.usage}')
			self.buffer_print('VOLTRON', f'Current Sound Command: !{self._sound_command}')
			return

		self._sound_data['sound_command'] = match.group(1)
		self.save_module_data(self._sound_data)
		self._sound_command = self._sound_data['sound_command']
		self.buffer_print('VOLTRON', f'Entrance sound command set to !{self._sound_command}')

	def _add_entrance_sound(self, input, command):
		match = re.search(r'^@?([^ ]+) ([^ ]+)$', input)

		if not match:
			self.buffer_print('VOLTRON', f'Usage: {command.usage}')
			return

		login = match.group(1)
		sound = match.group(2)

		broadcaster = get_broadcaster()
		api = broadcaster.twitch_api
		user_info = api.get_user(login)

		if not user_info:
			self.buffer_print('VOLTRON', f'User not found: {login}')
			return

		self._sound_data['user_sounds'][user_info['id']] = {
			'sound_file': sound,
			'display_name': user_info['display_name'],
			'login': user_info['login']
		}
		self.save_module_data(self._sound_data)

		display_name = user_info['display_name']
		self.buffer_print('VOLTRON', f'Sound ({sound}) added for {display_name}')

	def _remove_entrance_sound(self, input, command):
		match = re.search(r'^([^ ]+)$', input)

		if not match:
			self.buffer_print('VOLTRON', f'Usage: {command.usage}')
			return

		login = match.group(1)

		user_info = get_broadcaster().twitch_api.get_user(login)
		if not user_info:
			self.buffer_print('VOLTRON', f'User not found: {login}')
			return

		if not user_info['id'] in self._sound_data['user_sounds'].keys():
			self.buffer_print('VOLTRON', f"No sound exists for user: {user_info['display_name']}")
			return

		del self._sound_data['user_sounds'][user_info['id']]
		self.save_module_data(self._sound_data)
		self.buffer_print('VOLTRON', f"Sound for {user_info['display_name']} removed.")

	def _list_entrance_sounds(self, input, command):
		self.buffer_print('VOLTRON', 'Entrance Sounds:')
		for user in self._sound_data['user_sounds']:
			sound_data = self._sound_data['user_sounds'][user]
			self.buffer_print('VOLTRON', f"  {sound_data['display_name']}: {sound_data['sound_file']}")

	@property
	def media_directory(self):
		return self.data_directory + '\\Media'

	def shutdown(self):
		self.save_module_data(self._sound_data)
