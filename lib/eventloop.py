import threading
import os
import sys
import time
from importlib import import_module
from queue import Queue
from playsound import playsound

from base.events import Event, TimerEvent, StreamStatusEvent
from lib.common import get_db, get_broadcaster, get_module_directory
from lib.TwitchAPIHelper import TwitchAPIHelper
import config

class BroadcastStatusThread(threading.Thread):
	def __init__(self, event_queue):
		threading.Thread.__init__(self)

		self.event_queue = event_queue
		self.last_check = 0
		self._keep_listening = True

		self.broadcast_id = None

	def run(self):
		while self._keep_listening:
			if time.time() - self.last_check > 30:
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

						self.broadcast_id = stream['id']

					else:
						if self.broadcast_id or self.last_check == 0:
							self.event_queue.put(StreamStatusEvent())

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
	def __init__(self, media_queue):
		threading.Thread.__init__(self)

		self.media_queue = media_queue
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
				playsound(media[1])

class EventLoop(threading.Thread):
	def __init__(self, voltron, buffer_queue, event_queue):
		threading.Thread.__init__(self)
		self.buffer_queue = buffer_queue
		self.event_queue = event_queue
		self.media_queue = Queue()

		self.modules = []
		self.voltron = voltron

		self.registered_listeners = {
			'CHATCOMMAND' : [],
			'CHATMESSAGE' : [],
			'TIMER' : [],
			'STREAM_STATUS': [],
			'FIRST_MESSAGE': []
		}

		self._keep_listening = True

	def run(self):
		con, cur = get_db()
		core_mods = next(os.walk('./CoreModules'))[1]
		for mod in core_mods:
			if mod[0] == '_':
				continue
			mod_instance = import_module('CoreModules.{}'.format(mod)).VoltronModule(self, self.voltron)
			self.modules.append(mod_instance)

		#mod_dir = config.APP_DIRECTORY + '\\Modules'
		mod_dir = get_module_directory()
		#manager = PluginManager()
		#manager.setPluginPlaces([mod_dir])
		#manager.collectPlugins()

		#for plugin in manager.getAllPlugins():
		#	self.voltron.buffer_queue.put(('VOLTRON', plugin.plugin_object.try_hard()))
		# sys.path.append(mod_dir)
		# if not os.path.isdir(mod_dir):
		# 	os.makedirs(mod_dir)
		#
		# mod_dirs = next(os.walk(mod_dir))[1]
		# for mod in mod_dirs:
		# 	self.voltron.buffer_queue.put(('VOLTRON', f'{mod_dir}\\{mod}\\'))
		# 	mod_import = import_module(f'{mod}.poop').Poop
		# 	poop = mod_import()
		# 	self.voltron.buffer_queue.put(('VOLTRON', poop.try_hard()))

		core_mods = next(os.walk('./Modules'))[1]
		for mod in core_mods:
			if mod[0] == '_':
				continue

			mod_import = import_module('Modules.{}'.format(mod)).VoltronModule
			mod_name = mod_import.module_name

			sql = 'SELECT * FROM modules WHERE module_name = ?'
			cur.execute(sql, (mod_name, ))
			res = cur.fetchone()
			if not res:
				sql = 'INSERT INTO modules (module_name, enabled) VALUES (?, ?)'
				cur.execute(sql, (mod_name, 1))
			elif not res['enabled']:
				continue

			mod_instance = mod_import(self, self.voltron)
			self.modules.append(mod_instance)

		con.commit()
		con.close()

		self.timer_thread = TimerEventThread(self.event_queue)
		self.timer_thread.start()

		self.media_thread = MediaThread(self.media_queue)
		self.media_thread.start()

		self.live_thread = BroadcastStatusThread(self.event_queue)
		self.live_thread.start()

		self.listen()

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
				callbacks = self.registered_listeners.get(event.type, [])
				for callback in callbacks:
					callback(event)
				#self.buffer_queue.put(('INFO', event.type))
		self.timer_thread.stop()
		self.timer_thread.join()

		self.media_queue.put('SHUTDOWN')
		#self.media_thread.stop()
		self.media_thread.join()

		self.live_thread.stop()
		self.live_thread.join()
