import re
import time

from lib.common import get_default_user
from base.module import ModuleBase, ModuleAdminCommand
from base.events import EVT_CHATCOMMAND, EVT_CHATMESSAGE

class Trigger(ModuleBase):
	module_name = 'trigger'
	internal_cd = 5

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
		if not 'cooldowns' in self._triggers:
			self._triggers['cooldowns'] = {}
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
			self._set_trigger_account,
			usage = f'{self.module_name} trigger_account trigger',
			description = 'Response account for triggers',
		))

		self.event_listen(EVT_CHATCOMMAND, self.command)
		self.event_listen(EVT_CHATMESSAGE, self.chat_message)

	def chat_message(self, event):
		if not self.regex:
			return
		words_re = re.findall(self.regex, event.message, re.IGNORECASE)

		words = []
		if words_re:
			[words.append(x.lower()) for x in words_re if x.lower() not in words]
		for word in words:
			if not word.lower() in self._triggers['triggers']:
				continue
			messages = self._triggers['triggers'][word.lower()].get('response', [])

			last_run = self._triggers['cooldowns'].get(word, 0)
			if time.time() - last_run < self.internal_cd:
				continue

			response_twitch_id = self._triggers['triggers'][word.lower()].get('account')

			for message in messages:
				self.send_chat_message(message, event=event, twitch_id=response_twitch_id)

			self._triggers['cooldowns'][word] = time.time()


	def command(self, event):
		if event.command in self._static_commands:
			self._static_commands[event.command](event)

	def _list_triggers(self, input, command):
		self.print('All tiggers:')
		for trigger in self._triggers['triggers']:
			self.print(f'  {trigger}')

	def _set_trigger_account(self, input, command):
		match = re.search('^([^ ]+)$', input)
		if not match:
			self.print(f'Usage: {command.usage}')
			return

		word = match.group(1).lower().strip()
		if not word in self._triggers['triggers']:
			self.print(f'No trigger configured for {word}')
			return


		def account_selected(account):
			self._triggers['triggers'][word]['account'] = account.twitch_user_id
			self.save_module_data(self._triggers)
			self.print(f"Response account for '{word}' set to {account.display_name}")


		self.select_account(account_selected)

	def _add_trigger(self, event):
		if not event.is_mod:
			self.send_chat_message(f"@{event.display_name} you are not a mod.")
			return

		match = re.search(r'^([^ ]+) (.*)', event.message)
		if match:
			trigger = match.group(1).lower()
			response = match.group(2).strip()
			if trigger in self._triggers['triggers']:
				self.send_chat_message(f"@{event.display_name} The trigger {trigger} already exists. You can delete it using !deletetrigger")
				return
			else:
				self._triggers['triggers'][trigger] = { 'response': [response] }

			self.save_module_data(self._triggers)
			self.send_chat_message(f'Trigger {trigger} successfully added!')

	def _append_trigger(self, event):
		if not event.is_mod:
			self.send_chat_message(f"@{event.display_name} you are not a mod.")
			return

		match = re.search(r'^([^ ]+) (.*)', event.message)
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

		match = re.search(r'^([^ ]+)$', event.message)
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
			or_str += r'\b' + re.escape(trigger) + r'\b|'

		if or_str:
			or_str = or_str[:-1]

		self.regex = r'({})'.format(or_str)

	def save_module_data(self, data):
		ModuleBase.save_module_data(self, data)
		self._compile_regex()

	def shutdown(self):
		self.save_module_data(self._triggers)
