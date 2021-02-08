from base.module import ModuleBase

from base.events import EVT_CHATMESSAGE, EVT_STREAM_STATUS, FirstMessageEvent

class EntranceEvents(ModuleBase):
	module_name = 'entrance_events'
	configurable = False
	def setup(self):
		self._users = self.get_module_data()
		if not 'active' in self._users:
			self._users['active'] = []

		self.event_listen(EVT_STREAM_STATUS, self.status_change)
		self.event_listen(EVT_CHATMESSAGE, self.chat_message)

	def status_change(self, event):
		current_id = self._users.get('stream_id', None)
		if event.is_live and current_id != event.stream_id:
			self._users['stream_id'] = event.stream_id
			self._users['active'] = []

		elif not event.is_live:
			self._users = {
				'stream_id': None,
				'active': []
			}

	def chat_message(self, event):
		if self._users.get('stream_id', None):
			if not event.user_id in self._users['active']:
				self._users['active'].append(event.user_id)
				self.event_loop.event_queue.put(FirstMessageEvent(
					event.message,
					event.display_name,
					event.user_id,
					event.is_vip,
					event.is_mod,
					event.is_broadcaster
				))
				self.save_module_data(self._users)
				if int(event.user_id) == 158126582:
					self.send_chat_message(f'Oh hai dad. @{event.display_name}')

	def shutdown(self):
		self.save_module_data(self._users)
