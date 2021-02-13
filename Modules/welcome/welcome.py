import re
import os
import sounddevice
import time
import humanize

from base.module import ModuleBase, ModuleAdminCommand
from lib.common import get_broadcaster
from base.events import EVT_FIRST_MESSAGE, EVT_CHATCOMMAND, EVT_STREAM_STATUS, ChatMessageEvent, ChatCommandEvent

class Welcome(ModuleBase):
	module_name = "welcome"
	def setup(self):
		if not os.path.isdir(self.media_directory):
			os.makedirs(self.media_directory)

		self._sound_data = self.get_module_data()
		self._sound_command = self._sound_data.get('sound_command', 'hi')
		self._stream_online = False
		if not 'user_sounds' in self._sound_data.keys():
			self._sound_data['user_sounds'] = {}

		self._last_alert = 0

		self.register_admin_command(ModuleAdminCommand(
			'command',
			self._set_command,
			usage = f'{self.module_name} command !<command>',
			description = 'Set command for users to play their welcome message & sound'
		))

		self.register_admin_command(ModuleAdminCommand(
			'sound',
			self._add_entrance_sound,
			usage = f'{self.module_name} sound <twitch_user> <sound.mp3>',
			description = 'Add entrance sound for <twitch_user> set <sound.mp3> to "none" to clear'
		))

		self.register_admin_command(ModuleAdminCommand(
			'volume',
			self._set_volume,
			usage = f'{self.module_name} volume <twitch_user> <volume>',
			description = 'Set volume for entrance sound in %. Default is 100.'
		))

		self.register_admin_command(ModuleAdminCommand(
			'message',
			self._add_entrance_message,
			usage = f'{self.module_name} message <twitch_user> <message>',
			description = 'Add entrance message for <twitch_user>. Set <message> to "none" to clear'
		))

		self.register_admin_command(ModuleAdminCommand(
			'remove',
			self._remove_entrance_sound,
			usage = f'{self.module_name} remove <twitch_user>',
			description = 'Remove entrance sound and message for <twitch_user>'
		))

		self.register_admin_command(ModuleAdminCommand(
			'list',
			self._list_entrance_sounds,
			usage = f'{self.module_name} list',
			description = 'List entrance sounds'
		))

		self.register_admin_command(ModuleAdminCommand(
			'dir',
			self._show_directory,
			usage = f'{self.module_name} dir',
			description = 'Show directory for audio files'
		))

		self.register_admin_command(ModuleAdminCommand(
			'audio_device',
			self._set_entrance_audio_device,
			usage = f'{self.module_name} audio_device',
			description = 'Set the audio device to use for entrance sounds'
		))

		self.register_admin_command(ModuleAdminCommand(
			'alert_audio_device',
			self._set_alert_audio_device,
			usage = f'{self.module_name} alert_audio_device',
			description = 'Set the audio device to use for entrance alerts'
		))

		self.register_admin_command(ModuleAdminCommand(
			'alert_sound',
			self._set_alert_sound,
			usage = f'{self.module_name} alert_sound <soundfile>',
			description = 'Set the sound file for entrance alerts. Set <soundfile> to "none" to clear.'
		))

		self.register_admin_command(ModuleAdminCommand(
			'test',
			self._test_welcome,
			usage = f'{self.module_name} test <user>',
			description = 'Test the welcome event for <user> if one is set.'
		))

		self.event_listen(EVT_FIRST_MESSAGE, self.send_first_message_command)
		self.event_listen(EVT_CHATCOMMAND, self.command)
		self.event_listen(EVT_STREAM_STATUS, self.status_change)

	def first_message(self, event, run_by_command=False, testing=False):
		handled = False
		if not self._stream_online and not testing:
			return False

		sound_played = False
		if event.user_id in self._sound_data['user_sounds']:
			data = self._sound_data['user_sounds'][event.user_id]

			if data.get('sound_file', None):
				sound_path = f"{self.media_directory}\\{data['sound_file']}"
				volume = data.get('volume', 100)
				if not os.path.isfile(sound_path):
					self.buffer_print('ERR', f'{sound_path} does not exist')

				else:
					self.play_audio(
						sound_path,
						device=self.entrance_sound_device,
						volume=volume
					)
					sound_played = True
					handled = True

			if data.get('message', None):
				self.send_chat_message(data['message'], event=event)
				handled = True

		since_alert = time.time() - self._last_alert
		if not sound_played and self.alert_sound_device is not None and self.alert_sound and not run_by_command and since_alert > 30:
			alert_path = f"{self.media_directory}\\{self.alert_sound}"
			if not os.path.isfile(alert_path):
				self.buffer_print('ERR', f'{alert_path} does not exist')
			else:
				self.play_audio(alert_path, device=self.alert_sound_device)
				self._last_alert = time.time()

		if not run_by_command:
			broadcaster = get_broadcaster()
			follow_str = "NOT FOLLOWING"
			follow_time = broadcaster.twitch_api.get_follow_time(broadcaster.twitch_user_id, event.user_id)
			if follow_time is not None:
				follow_str = f"Followed {humanize.naturaltime(follow_time)}"
			self.buffer_print('VOLTRON', f'First message: {event.display_name} ({follow_str})')

		return handled

	def status_change(self, event):
		if event.is_live:
			self._stream_online = True
		else:
			self._stream_online = False

	def command(self, event):
		if event.command != self._sound_command:
			return False

		run_by_command = True
		if hasattr(event, 'run_by_command'):
			run_by_command = event.run_by_command

		return self.first_message(event, run_by_command=run_by_command)


	def send_first_message_command(self, event):
		command = ChatCommandEvent(
			self._sound_command,
			event.message,
			event.display_name,
			event.user_id,
			event.is_vip,
			event.is_mod,
			event.is_broadcaster,
			bypass_permissions = False,
			run_by_command = False
		)

		self.event_loop.event_queue.put(command)

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
		if sound.lower() == 'none':
			sound = None

		broadcaster = get_broadcaster()
		api = broadcaster.twitch_api
		user_info = api.get_user(login)

		if not user_info:
			self.buffer_print('VOLTRON', f'User not found: {login}')
			return

		if user_info['id'] not in self._sound_data['user_sounds']:
			self._sound_data['user_sounds'][user_info['id']] = {}

		self._sound_data['user_sounds'][user_info['id']]['sound_file'] = sound
		self._sound_data['user_sounds'][user_info['id']]['display_name'] = user_info['display_name']
		self._sound_data['user_sounds'][user_info['id']]['login'] = user_info['login']

		self.save_module_data(self._sound_data)

		display_name = user_info['display_name']
		self.buffer_print('VOLTRON', f'Sound ({sound}) added for {display_name}')

	def _set_alert_sound(self, input, command):
		match = re.search(r'^([^ ]+)$', input)
		if not match:
			self.buffer_print('VOLTRON', f'Usage: {command.usage}')
			return

		sound_file = match.group(1)

		if sound_file.lower() == 'none':
			del self._sound_data['alert_sound']
		else:
			self._sound_data['alert_sound'] = sound_file
		self.buffer_print('VOLTRON', f'Alert sound set to {sound_file}')
		self.save_module_data(self._sound_data)

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
		self.buffer_print('VOLTRON', 'Welcome Events:')
		for user in self._sound_data['user_sounds']:
			sound_data = self._sound_data['user_sounds'][user]
			self.buffer_print('VOLTRON', f"  {sound_data['display_name']}:")
			sound_file = sound_data.get('sound_file', 'None')
			message = sound_data.get('message', 'None')
			self.buffer_print('VOLTRON', f'    Sound File: {sound_file}')
			if sound_file:
				self.buffer_print('VOLTRON', f"    Volume: {sound_data.get('volume', 100)}%")
			self.buffer_print('VOLTRON', f'    message: {message}')

	def _show_directory(self, input, command):
		self.buffer_print('VOLTRON', 'Media Directory:')
		self.buffer_print('VOLTRON', self.media_directory)

	def _select_audio_device(self, key):
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

		self.buffer_print('VOLTRON', f"Current audio device: {self._sound_data.get(key, 'Default')}")

		def save(prompt):
			if prompt.strip() == 'c':
				self.update_status_text()
				return True

			if prompt == "-1":
				if key in self._sound_data:
					del self._sound_data[key]
					self.save_module_data(self._sound_data)
				self.buffer_print('VOLTRON', 'Audio device set to default')
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

			self._sound_data[key] = device_name
			self.save_module_data(self._sound_data)
			self.update_status_text()
			self.buffer_print('VOLTRON', f"Audio device set to {device['name']}")
			return True

		self.update_status_text('Select Audio Device. -1 for default. c to cancel.')
		self.prompt_ident = self.get_prompt('Audio Device> ', save)

	def _set_entrance_audio_device(self, input, command):
		self._select_audio_device('entrance_sound_device')

	def _add_entrance_message(self, input, command):
		match = re.search(r'^@?([^ ]+) (.+)$', input)

		if not match:
			self.buffer_print('VOLTRON', f'Usage: {command.usage}')
			return

		login = match.group(1)
		message = match.group(2)
		if message.lower() == 'none':
			message = None

		broadcaster = get_broadcaster()
		api = broadcaster.twitch_api
		user_info = api.get_user(login)

		if not user_info:
			self.buffer_print('VOLTRON', f'User not found: {login}')
			return

		if user_info['id'] not in self._sound_data['user_sounds']:
			self._sound_data['user_sounds'][user_info['id']] = {}

		self._sound_data['user_sounds'][user_info['id']]['message'] = message
		self._sound_data['user_sounds'][user_info['id']]['display_name'] = user_info['display_name']
		self._sound_data['user_sounds'][user_info['id']]['login'] = user_info['login']

		self.save_module_data(self._sound_data)

		display_name = user_info['display_name']
		self.buffer_print('VOLTRON', f'Message added for {display_name}')

	def _set_alert_audio_device(self, input, command):
		self._select_audio_device('alert_sound_device')

	def _set_volume(self, input, command):
		match = re.search(r'^([^ ]+) (\d+)$', input)
		if not match:
			self.buffer_print('VOLTRON', f'Usage: {command.usage}')
			return

		login = match.group(1)
		volume = int(match.group(2))

		broadcaster = get_broadcaster()
		api = broadcaster.twitch_api
		user_info = api.get_user(login)

		if not user_info:
			self.buffer_print('VOLTRON', f'User not found: {login}')
			return

		if user_info['id'] not in self._sound_data['user_sounds']:
			self.buffer_print('VOLTRON', f'Welcome not configured for: {user_info["display_name"]}')
			return

		self._sound_data['user_sounds'][user_info['id']]['volume'] = volume
		self.save_module_data(self._sound_data)
		self.buffer_print('VOLTRON', f"Volume for {user_info['display_name']} set to {volume}%")

	def _test_welcome(self, input, command):
		match = re.search(r'^([^ ]+)$', input)

		if not match:
			self.buffer_print('VOLTRON', f'Usage: {command.usage}')
			return

		login = match.group(1)

		broadcaster = get_broadcaster()
		api = broadcaster.twitch_api
		user_info = api.get_user(login)

		if not user_info:
			self.buffer_print('VOLTRON', f'User not found: {login}')
			return

		event = ChatMessageEvent(
			'',
			user_info['display_name'],
			user_info['id'],
			False,
			False,
			False
		)

		self.first_message(event, testing=True, run_by_command=True)

	@property
	def media_directory(self):
		return self.data_directory + '\\Media'

	@property
	def entrance_sound_device(self):
		device = self._sound_data.get('entrance_sound_device', None)
		if device is None:
			return None
		elif device.isdigit():
			return int(device)
		return device

	@property
	def alert_sound_device(self):
		device = self._sound_data.get('alert_sound_device', None)
		if device is None:
			return None
		elif device.isdigit():
			return int(device)
		return device

	@property
	def alert_sound(self):
		return self._sound_data.get('alert_sound', None)

	def shutdown(self):
		self.save_module_data(self._sound_data)
