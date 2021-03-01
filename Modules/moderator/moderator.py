from base.module import ModuleBase
from base.events import EVT_CHATCOMMAND
from lib.common import get_broadcaster

class ModeratorModule(ModuleBase):
	module_name = 'moderator'
	def setup(self):
		self._module_data = self.get_module_data()

		self._command_map = {
			'settitle': self._set_title,
			'setgame': self._set_game
		}

		self.event_listen(EVT_CHATCOMMAND, self.command)

	def command(self, event):
		if not event.command in self._command_map:
			return

		if not event.is_mod:
			return

		self._command_map[event.command](event)

	def _set_title(self, event):
		if not event.message:
			return
		broadcaster = get_broadcaster()

		res = self.twitch_api.set_stream_title(broadcaster.twitch_user_id, event.message)
		if res:
			self.send_chat_message('Stream title set to:')
			self.send_chat_message(res['title'])
		else:
			self.send_chat_message('Error updating stream title')

	def _set_game(self, event):
		if not event.message:
			return

		broadcaster = get_broadcaster()

		stream_info = self.twitch_api.set_stream_game(broadcaster.twitch_user_id, event.message)
		if stream_info:
			game_name = stream_info['game_name']
			self.send_chat_message(f'Game set to "{game_name}"')
		else:
			self.send_chat_message('Error setting game.')

	def shutdown(self):
		self.save_module_data(self._module_data)
