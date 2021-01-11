import threading
import os
import sys
import time
from importlib import import_module
from queue import Queue
import sounddevice
import audio2numpy
from audio2numpy.exceptions import AudioFormatError
import numpy
from math import sqrt

from base.events import Event, TimerEvent, StreamStatusEvent, EVT_CHATCOMMAND
from lib.common import get_db, get_broadcaster, get_module_directory
from lib.TwitchAPIHelper import TwitchAPIHelper
import config

sys.path.append(config.APP_DIRECTORY)

class BroadcastStatusThread(threading.Thread):
	def __init__(self, event_queue, buffer_queue):
		threading.Thread.__init__(self)

		self.event_queue = event_queue
		self.buffer_queue = buffer_queue
		self.last_check = 0
		self.last_changed = 0
		self._keep_listening = True

		self.broadcast_id = None

	def run(self):
		while self._keep_listening:
			if (time.time() - self.last_check > 30) and (time.time() - self.last_changed > 180):
				broadcaster = get_broadcaster()
				if broadcaster:
					api = TwitchAPIHelper(broadcaster.oauth_tokens)
					stream = api.get_stream(broadcaster.twitch_user_id)
					if stream:
						if not self.broadcast_id or self.last_check == 0:
							self.event_queue.put(StreamStatusEvent(
								stream_id = stream['id'],
								title = stream['title'],
								started_at = stream['started_at'],
								viewer_count = stream['viewer_count']
							))
							self.last_changed = time.time()
							self.buffer_queue.put(('VOLTRON', 'Stream is now live!'))
							self.buffer_queue.put(('DEBUG', f"Stream ID: {stream['id']}"))

						self.broadcast_id = stream['id']

					else:
						if self.broadcast_id or self.last_check == 0:
							self.event_queue.put(StreamStatusEvent())
							self.last_changed = time.time()
							self.buffer_queue.put(('INFO', 'Stream is offline.'))

						self.broadcast_id = None

				self.last_check = time.time()

			time.sleep(1)

	def stop(self):
		self._keep_listening = False

class TimerEventThread(threading.Thread):
	def __init__(self, event_queue):
		threading.Thread.__init__(self)

		self.event_queue = event_queue
		self._keep_listening = True

	def run(self):
		while self._keep_listening:
			time.sleep(1)

			self.event_queue.put(TimerEvent())

	def stop(self):
		self._keep_listening = False

class MediaThread(threading.Thread):
	def __init__(self, media_queue, buffer_queue):
		threading.Thread.__init__(self)

		self.media_queue = media_queue
		self.buffer_queue = buffer_queue
		self._keep_listening = True

	def run(self):
		while self._keep_listening:
			media = self.media_queue.get()

			if media == 'SHUTDOWN':
				self._keep_listening = False
				break

			if len(media) < 2:
				continue

			if media[0] == 'audio':
				kwargs = {}
				if len(media) >= 3:
					kwargs = media[2]
				device = kwargs.get('device', None)
				volume = kwargs.get('volume', 100)

				try:
					data, fs = audio2numpy.open_audio(media[1])
				except AudioFormatError:
					self.buffer_queue.put(('ERR', 'Invalid File Format:'))
					self.buffer_queue.put(('ERR', media[1]))
					self.buffer_queue.put(('ERR', 'Accepted file formats: .wav .mp3'))
					continue

				if volume != 100 and type(volume) == int:
					factor = volume / 100
					multiplier = pow(2, (sqrt(sqrt(sqrt(factor))) * 192 - 192)/6)
					numpy.multiply(data, multiplier, out=data, casting='unsafe')

				sounddevice.play(data, fs, device=device)
				sounddevice.wait()

class EventLoop(threading.Thread):
	def __init__(self, voltron, buffer_queue, event_queue):
		threading.Thread.__init__(self)
		self.buffer_queue = buffer_queue
		self.event_queue = event_queue
		self.media_queue = Queue()
		self._core_mod_names = []

		self.modules = []
		self.cooldown_module = None
		self.permission_module = None
		self.voltron = voltron

		self.registered_listeners = {
			'CHATCOMMAND' : [],
			'CHATMESSAGE' : [],
			'TIMER' : [],
			'STREAM_STATUS': [],
			'FIRST_MESSAGE': [],
			'SUBSCRIPTION': [],
			'BITS': [],
			'POINT_REDEMPTION': []
		}

		self._keep_listening = True

	def run(self):
		core_mods = next(os.walk('./CoreModules'))[1]
		for mod in core_mods:
			if mod[0] == '_':
				continue
			mod_instance = import_module('CoreModules.{}'.format(mod)).VoltronModule(self, self.voltron)
			self._core_mod_names.append(mod_instance.module_name)
			self.modules.append(mod_instance)

			if mod_instance.module_name == 'cooldown':
				self.cooldown_module = mod_instance
			elif mod_instance.module_name == 'permission':
				self.permission_module = mod_instance

		self.update_modules()

		self.timer_thread = TimerEventThread(self.event_queue)
		self.timer_thread.start()

		self.media_thread = MediaThread(self.media_queue, self.buffer_queue)
		self.media_thread.start()

		self.live_thread = BroadcastStatusThread(self.event_queue, self.buffer_queue)
		self.live_thread.start()

		self.listen()

	def update_modules(self):
		con, cur = get_db()
		mod_dir = get_module_directory()

		core_mods = next(os.walk('./Modules'))[1]
		user_mods = next(os.walk(mod_dir))[1]
		core_mods += user_mods
		module_names = []
		for mod in core_mods:
			if mod[0] == '_':
				continue

			if not mod in user_mods:
				mod_import = import_module('Modules.{}'.format(mod)).VoltronModule
			else:
				mod_import = import_module('UserModules.{}'.format(mod)).VoltronModule

			mod_name = mod_import.module_name
			if mod_name in self._core_mod_names:
				self.buffer_queue.put(('ERR', f'Invalid Module Name: {mod_name}'))
				continue

			module_names.append(mod_name)
			sql = 'SELECT * FROM modules WHERE module_name = ?'
			cur.execute(sql, (mod_name, ))
			res = cur.fetchone()
			if not res:
				sql = 'INSERT INTO modules (module_name, enabled) VALUES (?, ?)'
				cur.execute(sql, (mod_name, 0))
				continue
			elif not res['enabled']:
				continue

			mod_instance = mod_import(self, self.voltron)
			self.modules.append(mod_instance)

		#module_names = []
		#for mod in self.modules:
		#	module_names.append(mod.module_name)

		sql = "DELETE FROM modules WHERE module_name NOT IN ({})".format(','.join('?' * len(module_names)))

		cur.execute(sql, module_names)
		res = cur.fetchall()

		con.commit()
		con.close()

	def get_all_commands(self, twitch_id, is_mod=False, is_broadcaster=False):
		commands = {}
		for mod in self.modules:
			mod_commands = mod.get_commands(twitch_id, is_mod, is_broadcaster)
			if mod_commands:
				commands[mod.module_name] = mod_commands

		return commands

	def register_event(self, event_type, callback, event_params):
		if event_type in self.registered_listeners:
			self.registered_listeners[event_type].append(callback)

	def listen(self):
		while self._keep_listening:
			event = self.event_queue.get()
			if event == 'SHUTDOWN':
				self._keep_listening = False
				for module in self.modules:
					module.shutdown()
				break
			elif isinstance(event, Event):
				if event.type == EVT_CHATCOMMAND and self.permission_module:
					if not self.permission_module.has_command_permission(event):
						continue
				if event.type == EVT_CHATCOMMAND and self.cooldown_module:
					if self.cooldown_module.event_on_cooldown(event):
						continue
				callbacks = self.registered_listeners.get(event.type, [])
				handled = False
				for callback in callbacks:
					if callback(event):
						handled = True

				if event.type == EVT_CHATCOMMAND and self.cooldown_module and handled:
					self.cooldown_module.update_runtimes(event)
				#self.buffer_queue.put(('INFO', event.type))
		self.timer_thread.stop()
		self.timer_thread.join()

		self.media_queue.put('SHUTDOWN')
		#self.media_thread.stop()
		self.media_thread.join()

		self.live_thread.stop()
		self.live_thread.join()
