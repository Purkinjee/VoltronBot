from base.module import ModuleBase, ModuleAdminCommand
from base.events import EVT_CHATMESSAGE, EVT_CHATCOMMAND

import re
import os
import time
import sounddevice

class SoundCommand(ModuleBase):
	module_name = "sound_command"
	def setup(self):
		self._commands = self.get_module_data()

		if not os.path.isdir(self.media_directory):
			os.makedirs(self.media_directory)

		if not 'commands' in self._commands:
			self._commands['commands'] = {}

		self.register_admin_command(ModuleAdminCommand(
			'add',
			self._add_command,
			usage = f'{self.module_name} add <!command> <soundfile.mp3>',
			description = 'Add sound command'
		))

		self.register_admin_command(ModuleAdminCommand(
			'list',
			self._list_commands,
			usage = f'{self.module_name} list',
			description = 'List sound commands'
		))

		self.register_admin_command(ModuleAdminCommand(
			'details',
			self._command_details,
			usage = f'{self.module_name} details !<command>',
			description = 'Details for !<command>'
		))

		self.register_admin_command(ModuleAdminCommand(
			'delete',
			self._delete_command,
			usage = f'{self.module_name} delete <!command>',
			description = 'Delete a sound command'
		))

		self.register_admin_command(ModuleAdminCommand(
			'audio_device',
			self._select_audio_device,
			usage = f'{self.module_name} audio_device',
			description = 'Set the sound device for sounds'
		))

		self.register_admin_command(ModuleAdminCommand(
			'volume',
			self._set_volume,
			usage = f'{self.module_name} volume <!command> <volume>',
			description = 'Set volume for sound in %. Default is 100.'
		))

		self.register_admin_command(ModuleAdminCommand(
			'dir',
			self._show_directory,
			usage = f'{self.module_name} dir',
			description = 'Show media directory for audio files'
		))

		self.event_listen(EVT_CHATCOMMAND, self.command)

	def command(self, event):
		command = self._commands['commands'].get(event.command, None)
		if not command:
			return False

		sound_path = f"{self.media_directory}\\{command['sound_file']}"
		volume = command.get('volume', 100)

		if not os.path.isfile(sound_path):
			self.buffer_print('ERR', f'{sound_path} does not exist')
			return True

		self.play_audio(sound_path, device=self.audio_device, volume=volume)

		return True

	def _select_audio_device(self, input, command):
		devices = sounddevice.query_devices()

		hostapi = None
		valid_devices = []
		for api in sounddevice.query_hostapis():
			match = re.search('DirectSound', api['name'], re.IGNORECASE)
			if match:
				hostapi = api['name']
				for device_id in api['devices']:
					device = sounddevice.query_devices()[device_id]
					if device['max_output_channels'] > 0:
						valid_devices.append(device)
						self.buffer_print('VOLTRON', f"{len(valid_devices)}. {device['name']}")

		self.buffer_print('VOLTRON', f'Current audio device: {self.audio_device}')

		def save(prompt):
			if prompt.strip() == 'c':
				self.update_status_text()
				return True
			if prompt.strip() == '-1':
				self._commands['audio_device'] = None
				self.save_module_data(self._commands)
				self.buffer_print('VOLTRON', 'Default audio device selected.')
				self.update_status_text()
				return True

			if not prompt.isdigit():
				return False

			device_id = int(prompt)
			if len(valid_devices) < device_id or device_id < 1:
				self.buffer_print('VOLTRON', 'Invalid Selection')
				return False

			device = valid_devices[device_id - 1]

			device_name = f"{device['name']}, {hostapi}"

			self._commands['audio_device'] = device_name
			self.save_module_data(self._commands)
			self.update_status_text()
			self.buffer_print('VOLTRON', f"Audio device set to {device['name']}")
			return True

		self.update_status_text('Select Audio Device. c to cancel. -1 to reset to default.')
		self.prompt_ident = self.get_prompt('Audio Device> ', save)

	def _set_volume(self, input, command):
		match = re.search(r'^!([^ ]+) (\d+)$', input)
		if not match:
			self.buffer_print('VOLTRON', f'Usage: {command.usage}')
			return

		command = match.group(1).lower()
		volume = int(match.group(2))

		if not command in self._commands['commands']:
			self.buffer_print('VOLTRON', f'Command not found: !{command}')
			return

		self._commands['commands'][command]['volume'] = volume
		self.save_module_data(self._commands)
		self.buffer_print('VOLTRON', f"Volume for !{command} set to {volume}%")

	def _add_command(self, input, command):
		match = re.search(r'^!([^ ]+) ([^ ]+)', input)
		if not match:
			self.buffer_print('VOLTRON', f'Usage: {command.usage}')
			return

		command = match.group(1)
		sound_file = match.group(2)

		if command in self._commands['commands']:
			self._commands['commands'][command]['sound_file'] = sound_file
		else:
			self._commands['commands'][command] = { 'sound_file': sound_file }

		self.save_module_data(self._commands)
		self.buffer_print('VOLTRON', f'Sound Command !{command} successfully added!')

	def _list_commands(self, input, command):
		self.buffer_print('VOLTRON', '')
		self.buffer_print('VOLTRON', 'Sound Commands:')

		count = 1
		command_list = []
		for command in self._commands['commands']:
			command_list.append(command)
			media_file = self._commands['commands'][command]['sound_file']
			volume = self._commands['commands'][command].get('volume', 100)
			self.buffer_print('VOLTRON', f"!{command}")
			self.buffer_print('VOLTRON', f'  File: {media_file}')
			self.buffer_print('VOLTRON', f'  Volume: {volume}%')

		self.buffer_print('VOLTRON', '')

		return command_list

	def _command_details(self, input, command):
		match = re.search(r'^!([^ ]+)$', input)
		if not match:
			self.buffer_print('VOLTRON', f'Usage: {self.module_name} details !<command>')
			return

		command = match.group(1)
		if not command in self._commands['commands']:
			self.buffer_print('VOLTRON', f'Unknown command: !{command}')
			return

		media_file = self._commands['commands'][command]['sound_file']

		self.buffer_print('VOLTRON', f'Details for !{command}:')
		self.buffer_print('VOLTRON', f'  File: {media_file}')


	def _delete_command(self, input, command):
		match = re.search(r'^!([^ ]+)$', input.strip())
		if not match:
			self.buffer_print('VOLTRON', f'Usage: {command.usage}')
			return

		selected_command = match.group(1)
		if not selected_command in self._commands['commands'].keys():
			self.buffer_print('VOLTRON', f'Unkown command !{selected_command}')
			return

		del self._commands['commands'][selected_command]
		self.save_module_data(self._commands)
		self.buffer_print('VOLTRON', f'Command !{selected_command} deleted')

	def _show_directory(self, input, command):
		self.buffer_print('VOLTRON', 'Media Directory:')
		self.buffer_print('VOLTRON', self.media_directory)

	@property
	def media_directory(self):
		return self.data_directory + '\\Media'

	@property
	def audio_device(self):
		device = self._commands.get('audio_device', None)
		if device is None:
			return None
		elif device.isdigit():
			return int(device)
		return device


	def shutdown(self):
		self.save_module_data(self._commands)
