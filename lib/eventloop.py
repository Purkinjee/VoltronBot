import threading
import os
import time
from importlib import import_module
from queue import Queue
from playsound import playsound

from base.events import Event, TimerEvent
from lib.common import get_db

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
			'TIMER' : []
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
