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
		self.default_cooldown = 10

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
			'mod_only',
			self._toggle_mod_only,
			usage = f'{self.module_name} mod_only !<command>',
			description = 'Toggle mod only permission for command'
		))

		self.register_admin_command(ModuleAdminCommand(
			'broadcaster_only',
			self._toggle_broadcaster_only,
			usage = f'{self.module_name} broadcaster_only !<command>',
			description = 'Toggle broadcaster only permission for command'
		))

		self.register_admin_command(ModuleAdminCommand(
			'cooldown',
			self._set_cooldown,
			usage = f'{self.module_name} cooldown !<command> <seconds>',
			description = 'Set cooldown for command in seconds.'
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
			return

		if command.get('mod_only', False) and not event.is_mod:
			return

		if command.get('broadcaster_only', False) and not event.is_broadcaster:
			return

		cooldown = command.get('cooldown', self.default_cooldown)
		elapsed = time.time() - command.get('runtime', 0)
		if elapsed < cooldown:
			remaining = int(cooldown - elapsed)
			self.send_chat_message(f'Command !{event.command} is on cooldown ({remaining}s)')
			return

		sound_path = f"{self.media_directory}\\{command['sound_file']}"

		if not os.path.isfile(sound_path):
			self.buffer_print('ERR', f'{sound_path} does not exist')
			return

		self._commands['commands'][event.command]['runtime'] = time.time()
		self.play_audio(sound_path, device=self.audio_device)

	def _select_audio_device(self, input, command):
		devices = sounddevice.query_devices()
		count = -1
		valid_devices = {}
		for device in devices:
			count += 1
			if device['max_output_channels'] < 1:
				continue
			dev_str = f"{count} {device['name']}"
			self.buffer_print('VOLTRON', dev_str)
			valid_devices[count] = device
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
			match = re.search(r'^(\d+)$', prompt)
			if not match:
				return False

			device_id = int(match.group(1))
			device = valid_devices.get(device_id, None)
			if not device:
				self.buffer_print('VOLTRON', 'Invalid Selection')
				return False

			self._commands['audio_device'] = prompt
			self.save_module_data(self._commands)
			self.update_status_text()
			self.buffer_print('VOLTRON', f"Audio device set to {valid_devices[device_id]['name']}")
			return True

		self.update_status_text('Select Audio Device. c to cancel. -1 to reset to default.')
		self.prompt_ident = self.get_prompt('Audio Device> ', save)

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
			self.buffer_print('VOLTRON', f"!{command} - {media_file}")

		self.buffer_print('VOLTRON', '')

		return command_list

	def _command_details(self, input, command):
		match = re.search(r'^!([^ ]+)$', input)
		if not match:
			self.buffer_print('VOLTRON', f'Usage: {self.module_name} details !<command>')
			return

		command = match.group(1)
		if not command in self._commands['commands']:
			self.buffer_print('VOLTRON', f'Unknown command: !{comand}')
			return

		media_file = self._commands['commands'][command]['sound_file']
		mod_only = self._commands['commands'][command].get('mod_only', False)
		broadcaster_only = self._commands['commands'][command].get('broadcaster_only', False)
		cooldown = self._commands['commands'][command].get('cooldown', 'Default')

		self.buffer_print('VOLTRON', f'Details for !{command}:')
		self.buffer_print('VOLTRON', f'  File: {media_file}')
		self.buffer_print('VOLTRON', f'  Mod Only: {mod_only}')
		self.buffer_print('VOLTRON', f'  Broadcaster Only: {broadcaster_only}')
		self.buffer_print('VOLTRON', f'  Cooldown: {cooldown}')


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

	def _toggle_mod_only(self, input, command):
		match = re.search(r'^!([^ ]+)$', input.strip())
		if not match:
			self.buffer_print('VOLTRON', f'Usage: {command.usage}')
			return

		selected_command = match.group(1)
		if not selected_command in self._commands['commands'].keys():
			self.buffer_print('VOLTRON', f'Unkown command !{selected_command}')
			return

		mod_only = not self._commands['commands'][selected_command].get('mod_only', False)
		self._commands['commands'][selected_command]['mod_only'] = mod_only
		self.save_module_data(self._commands)

		self.buffer_print('VOLTRON', f'Command !{selected_command} updated (mod_only={mod_only})')

	def _toggle_broadcaster_only(self, input, command):
		match = re.search(r'^!([^ ]+)$', input.strip())
		if not match:
			self.buffer_print('VOLTRON', f'Usage: {command.usage}')
			return

		selected_command = match.group(1)
		if not selected_command in self._commands['commands'].keys():
			self.buffer_print('VOLTRON', f'Unkown command !{selected_command}')
			return

		broadcaster_only = not self._commands['commands'][selected_command].get('broadcaster_only', False)
		self._commands['commands'][selected_command]['broadcaster_only'] = broadcaster_only
		self.save_module_data(self._commands)

		self.buffer_print('VOLTRON', f'Command !{selected_command} updated (broadcaster_only={broadcaster_only})')

	def _set_cooldown(self, input, command):
		match = re.search(r'^!([^ ]+) ([0-9]+)$', input)
		if not match:
			self.buffer_print('VOLTRON', f'Usage: {command.usage}')
			return

		command = match.group(1)
		cooldown = int(match.group(2))

		if not command in self._commands['commands']:
			self.buffer_print('VOLTRON', f'Unkown command !{command}')
			return

		self._commands['commands'][command]['cooldown'] = cooldown
		self.buffer_print('VOLTRON', f'Cooldown for !{command} set to {cooldown}s')

	def _show_directory(self, input, command):
		self.buffer_print('VOLTRON', 'Media Directory:')
		self.buffer_print('VOLTRON', self.media_directory)

	@property
	def media_directory(self):
		return self.data_directory + '\\Media'

	@property
	def audio_device(self):
		device = self._commands.get('audio_device', None)
		if device is not None:
			device = int(device)
		return device


	def shutdown(self):
		self.save_module_data(self._commands)
