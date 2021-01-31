from base.module import ModuleBase, ModuleAdminCommand
from base.events import EVT_CHATCOMMAND

import re

class PermissionModule(ModuleBase):
	module_name = 'permission'
	def setup(self):
		self._permission_data = self.get_module_data()

		if not 'commands' in self._permission_data:
			self._permission_data['commands'] = {}

		self.register_admin_command(ModuleAdminCommand(
			'set',
			self._set_permission,
			usage = f'{self.module_name} set !<command> <all/vip/mod/broadcaster>',
			description = 'Set the permssion for !<command> to all, mod only, or broadcaster only'
		))

		self.register_admin_command(ModuleAdminCommand(
			'list',
			self._list_permissions,
			usage = f'{self.module_name} list',
			description = 'List all permissions'
		))

		self.register_admin_command(ModuleAdminCommand(
			'delete',
			self._delete_permission,
			usage = f'{self.module_name} delete !<command>',
			description = 'Delete permissions for !<command>'
		))

		self.register_admin_command(ModuleAdminCommand(
			'default',
			self._set_default_permission,
			usage = f'{self.module_name} default <all/vip/mod/broadcaster>',
			description = 'Set default permission for all comamnds to all, mod only, or broadcaster only'
		))

	def has_command_permission(self, event):
		if event.bypass_permissions:
			return True
		command_permission_data = self._permission_data['commands'].get(event.command, {})
		permission = command_permission_data.get('basic', self.default_permission)

		if permission == 'all':
			return True
		elif permission == 'broadcaster' and not event.is_broadcaster:
			return False
		elif permission == 'mod' and not event.is_mod:
			return False
		elif permission == 'vip' and not (event.is_vip or event.is_mod or event.is_broadcaster):
			return False

		return True

	def _set_permission(self, input, command):
		match = re.search(r'^!([^ ]+) (all|vip|mod|broadcaster)$', input)
		if not match:
			self.buffer_print('VOLTRON', f'Usage: {command.usage}')
			return

		command = match.group(1)
		permission = match.group(2)

		command_permission = self._permission_data['commands'].get(command, {})
		command_permission['basic'] = permission

		self._permission_data['commands'][command] = command_permission
		self.save_module_data(self._permission_data)

		self.buffer_print('VOLTRON', f'Permission for !{command} set to {permission}')

	def _delete_permission(self, input, command):
		match = re.search(r'^!([^ ]+)$', input)
		if not match:
			self.buffer_print('VOLTRON', f'Usage: {command.usage}')
			return

		command = match.group(1)
		if not command in self._permission_data['commands']:
			self.buffer_print('VOLTRON', f'Permission for !{command} does not exist')
			return

		del self._permission_data['commands'][command]
		self.save_module_data(self._permission_data)
		self.buffer_print('VOLTRON', f'Permission for !{command} deleted')

	def _list_permissions(self, input, command):
		self.buffer_print('VOLTRON', 'All permissions:')
		for command in self._permission_data['commands']:
			basic_permission = self._permission_data['commands'][command].get('basic', 'default')
			self.buffer_print('VOLTRON', f'  !{command}: {basic_permission}')
		self.buffer_print('VOLTRON', f'Default permission: {self.default_permission}')

	def _set_default_permission(self, input, command):
		if not input in ('all', 'vip', 'mod', 'broadcaster'):
			self.buffer_print('VOLTRON', f'Usage: {command.usage}')
			self.buffer_print('VOLTRON', f'Default permission: {self.default_permission}')
			return

		self._permission_data['default'] = input
		self.save_module_data(self._permission_data)
		self.buffer_print('VOLTRON', f'Default permission set to {input}')


	def shutdown(self):
		self.save_module_data(self._permission_data)

	@property
	def default_permission(self):
		return self._permission_data.get('default', 'all')
