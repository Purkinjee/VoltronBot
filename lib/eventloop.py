import threading
import os
from importlib import import_module

from base.events import Event

class EventLoop(threading.Thread):
	def __init__(self, voltron, buffer_queue, event_queue):
		threading.Thread.__init__(self)
		self.buffer_queue = buffer_queue
		self.event_queue = event_queue
		self.modules = []
		self.voltron = voltron

		self.registered_listeners = {
			'CHATCOMMAND' : []
		}

		self._keep_listening = True

	def run(self):
		core_mods = next(os.walk('./CoreModules'))[1]
		for mod in core_mods:
			if mod[0] == '_':
				continue
			mod_instance = import_module('CoreModules.{}'.format(mod)).VoltronModule(self, self.voltron)
			self.modules.append(mod_instance)

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
