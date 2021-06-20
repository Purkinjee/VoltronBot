from base.module import ModuleBase, ModuleAdminCommand
from base.events import EVT_CHATCOMMAND, ChatCommandEvent

import re
import random

class RandomModule(ModuleBase):
	module_name = 'random'
	def setup(self):
		self._module_data = self.get_module_data()
		if not 'commands' in self._module_data:
			self._module_data['commands'] = {}

		self.register_admin_command(ModuleAdminCommand(
			'add',
			self._add_random_command,
			usage = f'{self.module_name} add !<newcommand> !<option1> !<option2>...',
			description = 'Add a new command that will execute another command at random'
		))

		self.register_admin_command(ModuleAdminCommand(
			'delete',
			self._delete_random_command,
			usage = f'{self.module_name} delete !<command>',
			description = 'Delete command !<command>'
		))

		self.register_admin_command(ModuleAdminCommand(
			'list',
			self._list_commands,
			usage = f'{self.module_name} list',
			description = 'List all random commands'
		))

		self.event_listen(EVT_CHATCOMMAND, self.command)

	def command(self, event):
		if event.command not in self._module_data['commands']:
			return

		rand_command = random.choice(self._module_data['commands'][event.command])
		command_event = ChatCommandEvent(
			rand_command,
			event.message,
			event.display_name,
			event.user_id,
			False,
			False,
			False,
			bypass_permissions = True,
			msg_id= None
		)
		self.event_loop.event_queue.put(command_event)


	def _add_random_command(self, input, command):
		match = re.search(r'^!([^ ]+)(\s![^ ]+)+$', input)
		if not match:
			self.print(f'Usage: {command.usage}')
			return

		new_command = match.group(1)
		command_list = re.findall(r'(?:\s+!([^ ]+))', input)
		if len(command_list) < 2:
			self.print('Must have at least 2 commands to use random')
			return

		if new_command in self._module_data['commands']:
			self.print(f'Command !{new_command} already exists in this module')
			return

		self._module_data['commands'][new_command] = command_list
		self.save_module_data(self._module_data)
		self.print(f'Command !{new_command} added!')

	def _delete_random_command(self, input, command):
		match = re.search(r'^!([^ ]+)$', input)
		if not match:
			self.print(f'Usage: {command.usage}')
			return

		del_command = match.group(1)
		if not del_command in self._module_data['commands']:
			self.print(f'Command !{del_command} does not exist')
			return

		del self._module_data['commands'][del_command]
		self.save_module_data(self._module_data)
		self.print(f'Command !{del_command} deleted')

	def _list_commands(self, input, command):
		for c in self._module_data['commands']:
			self.print(f'!{c}:')
			for random in self._module_data['commands'][c]:
				self.print(f'  !{random}')


	def shutdown(self):
		self.save_module_data(self._module_data)
