from base.module import ModuleBase, ModuleAdminCommand
from base.events import EVT_CHATMESSAGE, EVT_CHATCOMMAND

import re
import os
import time
from playsound import playsound

class SoundCommand(ModuleBase):
	module_name = "sound_command"
	def setup(self):
		self._commands = self.get_module_data()
		self.default_cooldown = 10

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
			'directory',
			self._set_directory,
			usage = f'{self.module_name} directory <full path>',
			description = 'Set directory for sound files.'
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

		sound_path = "{directory}\\{sound_file}".format(
			directory = self.sound_dir,
			sound_file = command['sound_file']
		)

		if not os.path.isfile(sound_path):
			self.buffer_print('ERR', f'{sound_path} does not exist')
			return

		self._commands['commands'][event.command]['runtime'] = time.time()
		self.play_audio(sound_path)

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

	def _set_directory(self, input, command):
		if not input:
			self.buffer_print('VOLTRON', f'Usage: {command.usage}')
			self.buffer_print('VOLTRON', f'Current directory: {self.sound_dir}')
			return

		is_dir = os.path.isdir(input)
		if not is_dir:
			self.buffer_print('VOLTRON', f'Invalid Directory: {input}')
			return

		self._commands['sound_dir'] = input
		self.buffer_print('VOLTRON', f'Audio directory set to {input}')

	@property
	def sound_dir(self):
		if not 'sound_dir' in self._commands:
			return "{profile}\\Voltron\\Audio".format(
				profile=os.environ['USERPROFILE']
			)
		else:
			return self._commands['sound_dir']


	def shutdown(self):
		self.save_module_data(self._commands)
