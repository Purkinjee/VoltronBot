from base.module import ModuleBase, ModuleAdminCommand
from base.events import EVT_CHATCOMMAND
import re

class SafeFormat(dict):
	def __missing__(self, key):
		return key.join('{}')

class ShoutOut(ModuleBase):
	module_name = "shoutout"
	def setup(self):
		self._shoutout_data = self.get_module_data()

		self.register_admin_command(ModuleAdminCommand(
			'command',
			self.set_command,
			usage = f'{self.module_name} command !<command>',
			description = 'Set chat command for shoutouts',
		))

		self.register_admin_command(ModuleAdminCommand(
			'message',
			self.set_message,
			usage = f'{self.module_name} message <message>',
			description = 'Set chat message for shoutouts. Avilable variables: {streamer}, {game}, {url}',
		))

		self.register_admin_command(ModuleAdminCommand(
			'account',
			self.set_response_account,
			usage = f'{self.module_name} account',
			description = 'Set the account to use for shoutouts',
		))

		self.event_listen(EVT_CHATCOMMAND, self.command)

	def command(self, event):
		if event.command == self.so_command:
			match = re.search(r'^@?([^ ]+)$', event.args)
			if match:
				so_user = match.group(1)
				twitch_user = self.twitch_api.get_user(so_user)
				if not twitch_user:
					return False

				twitch_channel = self.twitch_api.get_channel(twitch_user['id'])

				chat_str = self.so_str.format_map(SafeFormat({
					'streamer' : twitch_user['display_name'],
					'game' : twitch_channel['game_name'],
					'url' : 'https://twitch.tv/{}'.format(twitch_user['login'])
				}))

				twitch_id = self._shoutout_data.get('account', None)
				self.send_chat_message(chat_str, twitch_id)

				return True

		return False

	def set_command(self, input, command):
		match = re.search(r'^!([^ ]+)$', input)

		if match:
			command = match.group(1)
			self._shoutout_data['command'] = command
			self.save_module_data(self._shoutout_data)

			self.buffer_print('VOLTRON', f"Shoutout command changed to !{command}")

		else:
			self.buffer_print('VOLTRON', f'Current command: !{self.so_command}')
			self.buffer_print('VOLTRON', f'Usage: {command.usage}')

	def set_message(self, input, command):
		if not input:
			self.buffer_print('VOLTRON', f'Usage: {command.usage}')
			self.buffer_print('VOLTRON', 'Available variables: {streamer}, {game}, {url}')
			self.buffer_print('VOLTRON', f'Current message: {self.so_str}')
			return

		self._shoutout_data['message'] = input
		self.save_module_data(self._shoutout_data)

		self.buffer_print('VOLTRON', 'Shoutout message updated:')
		self.buffer_print('VOLTRON', self.so_str)

	def set_response_account(self, input, command):
		def account_selected(account):
			self._shoutout_data['account'] = account.twitch_user_id
			self.save_module_data(self._shoutout_data)

		self.select_account(account_selected)

	@property
	def so_str(self):
		return self._shoutout_data.get('message', 'Go check out {streamer}. They were last playing {game}. {url}')

	@property
	def so_command(self):
		return self._shoutout_data.get('command', 'check')

	def shutdown(self):
		self.save_module_data(self._shoutout_data)
