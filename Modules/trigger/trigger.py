import re

from lib.common import get_default_user
from base.module import ModuleBase, ModuleAdminCommand
from base.events import EVT_CHATCOMMAND, EVT_CHATMESSAGE

class Trigger(ModuleBase):
	module_name = 'trigger'

	def setup(self):
		self.regex = r''
		self._static_commands = {
			'addtrigger': self._add_trigger,
			'appendtrigger': self._append_trigger,
			'deletetrigger': self._delete_trigger,
		}

		self._triggers = self.get_module_data()
		if not 'triggers' in self._triggers:
			self._triggers['triggers'] = {}
		self._compile_regex()

		self.default_user = get_default_user()

		self.register_admin_command(ModuleAdminCommand(
			'list',
			self._list_triggers,
			usage = f'{self.module_name} list',
			description = 'List all triggers',
		))

		self.register_admin_command(ModuleAdminCommand(
			'account',
			self._set_account,
			usage = f'{self.module_name} account',
			description = 'Response account for triggers',
		))

		self.event_listen(EVT_CHATCOMMAND, self.command)
		self.event_listen(EVT_CHATMESSAGE, self.chat_message)

	def chat_message(self, event):
		if not self.regex:
			return
		if int(event.user_id) == int(self.response_twitch_id):
			return
		words_re = re.findall(self.regex, event.message, re.IGNORECASE)
		words = []
		if words_re:
			[words.append(x.lower()) for x in words_re if x.lower() not in words]
		for word in words:
			if not word.lower() in self._triggers['triggers']:
				continue
			messages = self._triggers['triggers'][word.lower()].get('response', [])
			for message in messages:
				self.send_chat_message(message, event=event, twitch_id=self.response_twitch_id)

	def command(self, event):
		if event.command in self._static_commands:
			self._static_commands[event.command](event)

	def _list_triggers(self, input, command):
		self.buffer_print('VOLTRON', 'All tiggers:')
		for trigger in self._triggers['triggers']:
			self.buffer_print('VOLTRON', f'  {trigger}')


	def _set_account(self, input, command):
		def account_selected(account):
			self._triggers['response_twitch_id'] = account.twitch_user_id
			self.save_module_data(self._triggers)

		self.select_account(account_selected)

	def _add_trigger(self, event):
		if not event.is_mod:
			self.send_chat_message(f"@{event.display_name} you are not a mod.")
			return

		match = re.search(r'^([^ ]+) (.*)', event.args)
		if match:
			trigger = match.group(1).lower()
			response = match.group(2).strip()
			if trigger in self._triggers['triggers']:
				self.send_chat_message(f"@{event.display_name} The trigger !{command} already exists. You can delete it using !deletetrigger")
				return
			else:
				self._triggers['triggers'][trigger] = { 'response': [response] }

			self.save_module_data(self._triggers)
			self.send_chat_message(f'Trigger {trigger} successfully added!')

	def _append_trigger(self, event):
		if not event.is_mod:
			self.send_chat_message(f"@{event.display_name} you are not a mod.")
			return

		match = re.search(r'^([^ ]+) (.*)', event.args)
		if match:
			trigger = match.group(1).lower()
			response = match.group(2).strip()

			if not trigger in self._triggers['triggers']:
				self.send_chat_message(f'Trigger {trigger} not found')
				return

			self._triggers['triggers'][trigger]['response'].append(response)
			self.save_module_data(self._triggers)
			self.send_chat_message(f'Trigger {trigger} successfully modified')

	def _delete_trigger(self, event):
		if not event.is_mod:
			self.send_chat_message(f"@{event.display_name} you are not a mod.")
			return

		match = re.search(r'^([^ ]+)$', event.args)
		if not match:
			self.send_chat_message('Usage: !deletetrigger <trigger>')
			return

		trigger = match.group(1).lower()
		if not trigger in  self._triggers['triggers'].keys():
			self.send_chat_message(f'Trigger {trigger} not found')
			return

		del self._triggers['triggers'][trigger]
		self.save_module_data(self._triggers)
		self.send_chat_message(f'Trigger {trigger} successfully deleted!')

	def _compile_regex(self):
		or_str = ''

		for trigger in self._triggers['triggers']:
			or_str += re.escape(trigger) + '|'

		if or_str:
			or_str = or_str[:-1]

		self.regex = r'({})'.format(or_str)

	def save_module_data(self, data):
		ModuleBase.save_module_data(self, data)
		self._compile_regex()

	def shutdown(self):
		self.save_module_data(self._triggers)

	@property
	def response_twitch_id(self):
		id = self._triggers.get('response_twitch_id', None)
		if not id:
			id = self.default_user.twitch_user_id
		return int(id)
