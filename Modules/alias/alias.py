from base.module import ModuleBase, ModuleAdminCommand
from base.events import EVT_CHATCOMMAND, ChatCommandEvent

import re
import threading
import time

class AliasModule(ModuleBase):
	module_name = 'alias'
	def setup(self):
		self._module_data = self.get_module_data()
		if not 'commands' in self._module_data:
			self._module_data['commands'] = {}

		self.register_admin_command(ModuleAdminCommand(
			'new',
			self._new_alias,
			usage = f'{self.module_name} new !<alias>',
			description = 'Register !<alias> as a new alias',
		))

		self.register_admin_command(ModuleAdminCommand(
			'add',
			self._add_alias_command,
			usage = f'{self.module_name} add !<alias>',
			description = 'Add a command for !<alias>. !<alias> must be registered using new.',
		))

		self.register_admin_command(ModuleAdminCommand(
			'list',
			self._list_alias,
			usage = f'{self.module_name} list',
			description = 'List all aliases',
		))

		self.register_admin_command(ModuleAdminCommand(
			'delete',
			self._delete_alias,
			usage = f'{self.module_name} delete !<alias>',
			description = 'Delete one or all entries for !<alias>',
		))

		self.event_listen(EVT_CHATCOMMAND, self.command)

	def command(self, event):
		if not event.command in self._module_data['commands']:
			return

		for seq in self._module_data['commands'][event.command]['sequence']:
			command_args = seq['command'].split()
			message = ' '.join(command_args[1:])
			if not message:
				message = event.message
			command_event = ChatCommandEvent(
				command_args[0],
				message,
				event.display_name,
				event.user_id,
				event.is_vip,
				event.is_mod,
				event.is_broadcaster,
				bypass_permissions = True,
				original_message = event.message,
				**event.kwargs
			)
			if seq['delay'] == 0:
				self.event_loop.event_queue.put(command_event)
			else:
				delay = seq['delay'] / 1000
				t = threading.Thread(
					target=self._delayed_event_queue,
					args=(
						command_event,
						delay
					)
				)
				t.start()

	def _delayed_event_queue(self, event, delay):
		time.sleep(delay)
		self.event_loop.event_queue.put(event)

	def _new_alias(self, input, command):
		match = re.search(r'^!([^ ]+)$', input)
		if not match:
			self.print(f'Usage: {command.usage}')
			return

		command = match.group(1)
		if command in self._module_data['commands']:
			self.print(f'Command !{command} already registered as an alias')
			return

		self._module_data['commands'][command] = {'sequence': []}
		self.print(f'!{command} is now registered as an alias')
		self.save_module_data(self._module_data)

	def _add_alias_command(self, input, command):
		match = re.search(r'^!([^ ]+)$', input)
		if not match:
			self.print(f'Usage: {command.usage}')
			return

		alias = match.group(1)
		if not alias in self._module_data['commands']:
			self.print(f'!{alias} is not registered as an alias')
			self.print(f'Use "alias new !{alias}" to register it')
			return

		seq = self._module_data['commands'][alias].get('sequence', [])
		self.print('New command will be inserted before selected entry')
		count = 1
		for entry in seq:
			self.print(f"  {count}. !{entry['command']} ({entry['delay']}ms)")
			count += 1
		self.print(f"  {count}. END")

		## Function for position in sequence
		def command_selected(command_num):
			if command_num.lower() == 'c':
				self.update_status_text()
				return True
			if not command_num.isdigit():
				return False

			command_num = int(command_num)
			if command_num > count or command_num < 1:
				return False

			sequence_index = command_num - 1

			## Function for new command to be added
			def sequence_command_selected(sequence_command):
				if sequence_command.lower() == 'c':
					self.update_status_text()
					return True
				match = re.search(r'^!([^ ]+.*)$', sequence_command.strip())
				if not match:
					return False
				sequence_command = match.group(1)

				## Function for delay to be input
				def delay_selected(delay):
					if delay.lower() == 'c':
						self.update_status_text()
						return True

					if not delay.isdigit():
						return False

					delay = int(delay)

					self._module_data['commands'][alias]['sequence'].insert(sequence_index, {
						'command': sequence_command,
						'delay': delay
					})
					self.save_module_data(self._module_data)
					self.print(f'Sequence updated for !{alias}')
					self.update_status_text()
					self.terminate_prompt(self.prompt_ident)
					return True

				self.update_status_text('Command delay in ms. c to cancel')
				self.terminate_prompt(self.prompt_ident)
				self.prompt_ident = self.get_prompt('delay > ', delay_selected)


			self.update_status_text('Command to execute (!<command>). c to cancel')
			self.terminate_prompt(self.prompt_ident)
			self.prompt_ident = self.get_prompt('command > ', sequence_command_selected)

		self.update_status_text('Select location of new command. c to cancel.')
		self.prompt_ident = self.get_prompt('Command # > ', command_selected)

	def _delete_alias(self, input, command):
		match = re.search(r'^!([^ ]+)$', input)
		if not match:
			self.print(f'Usage: {command.usage}')
			return

		alias = match.group(1)
		if not alias in self._module_data['commands']:
			self.print(f'!{alias} is not registered as an alias')
			return

		seq = self._module_data['commands'][alias].get('sequence', [])
		count = 0
		for entry in seq:
			count += 1
			self.print(f"  {count}. !{entry['command']} ({entry['delay']}ms)")

		def delete_entry(entry):
			if entry.lower() == 'c':
				self.update_status_text()
				return True
			if entry.lower() == 'all':
				del self._module_data['commands'][alias]
				self.save_module_data(self._module_data)
				self.print(f'Alias !{alias} has been deleted')
				self.update_status_text()
				return True

			if not entry.isdigit():
				return False

			entry_index = int(entry) - 1
			if entry_index < 0 or (entry_index + 1) > len(self._module_data['commands'][alias]['sequence']):
				return False

			del self._module_data['commands'][alias]['sequence'][entry_index]
			self.print('Entry deleted')
			self.update_status_text()
			return True

		self.update_status_text('Select entry to delete. Type "all" for all entries, "c" to cancel')
		self.prompt_ident = self.get_prompt('Entry > ', delete_entry)

	def _list_alias(self, input, command):
		self.print('All aliases:')
		for alias in self._module_data['commands']:
			self.print(f'!{alias}')
			for seq in self._module_data['commands'][alias]['sequence']:
				self.print(f"  > !{seq['command']} ({seq['delay']}ms)")

	def shutdown(self):
		self.save_module_data(self._module_data)
