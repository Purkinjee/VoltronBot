import re

from lib.common import get_default_user
from base.module import ModuleBase
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
		self._compile_regex()

		self.default_user = get_default_user()

		self.event_listen(EVT_CHATCOMMAND, self.command)
		self.event_listen(EVT_CHATMESSAGE, self.chat_message)

	def chat_message(self, event):
		if not self.regex:
			return
		if int(event.user_id) == int(self.default_user.twitch_user_id):
			return
		words_re = re.findall(self.regex, event.message, re.IGNORECASE)
		words = []
		if words_re:
			[words.append(x.lower()) for x in words_re if x.lower() not in words]
		for word in words:
			if not word.lower() in self._triggers:
				continue
			messages = self._triggers[word.lower()].get('response', [])
			for message in messages:
				self.send_chat_message(message, event=event)

	def command(self, event):
		if event.command in self._static_commands:
			self._static_commands[event.command](event)

	def _add_trigger(self, event):
		if not event.is_mod:
			self.send_chat_message(f"@{event.display_name} you are not a mod.")
			return

		match = re.search(r'^([^ ]+) (.*)', event.args)
		if match:
			trigger = match.group(1).lower()
			response = match.group(2).strip()
			if trigger in self._triggers:
				self.send_chat_message(f"@{event.display_name} The command !{command} already exists. You can delete it using !deletecommand")
				return
			else:
				self._triggers[trigger] = { 'response': [response] }

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

			if not trigger in self._triggers:
				self.send_chat_message(f'Trigger {trigger} not found')
				return

			self._triggers[trigger]['response'].append(response)
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
		if not trigger in  self._triggers.keys():
			self.send_chat_message(f'Trigger {trigger} not found')
			return

		del self._triggers[trigger]
		self.save_module_data(self._triggers)
		self.send_chat_message(f'Trigger {trigger} successfully deleted!')

	def _compile_regex(self):
		or_str = ''

		for trigger in self._triggers:
			or_str += re.escape(trigger) + '|'

		if or_str:
			or_str = or_str[:-1]

		self.regex = r'({})'.format(or_str)

	def save_module_data(self, data):
		ModuleBase.save_module_data(self, data)
		self._compile_regex()

	def shutdown(self):
		self.save_module_data(self._triggers)
