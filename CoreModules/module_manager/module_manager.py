from base.module import ModuleBase, ModuleAdminCommand
import re
from lib.common import get_db

class ModuleManager(ModuleBase):
	module_name = "module"
	def setup(self):
		self.register_admin_command(ModuleAdminCommand(
			'toggle',
			self.toggle_module,
			usage = f'{self.module_name} toggle <module name>',
			description = 'Enable or disable module'
		))

		self.register_admin_command(ModuleAdminCommand(
			'list',
			self.list_modules,
			usage = f'{self.module_name} list',
			description = 'List all modules'
		))

	def toggle_module(self, input, command):
		match = re.search(r'^([^ ]+)$', input.strip())
		if not match:
			self.buffer_print('VOLTRON', f'Usage: {command.usage}')
			return

		module_name = match.group(1)

		con, cur = get_db()

		sql = "SELECT * FROM modules WHERE module_name = ?"
		cur.execute(sql, (module_name, ))
		res = cur.fetchone()

		if not res:
			self.buffer_print('VOLTRON', f'Module not found: {module_name}')
			con.commit()
			con.close()
			return

		enabled = not res['enabled']
		sql = "UPDATE modules SET enabled = ? WHERE id = ?"
		cur.execute(sql, (enabled, res['id']))

		enabled_str = 'enabled' if enabled else 'disabled'
		self.buffer_print('VOLTRON', f'Module {module_name} has been {enabled_str}')
		self.buffer_print('STATUS', 'Modules changed. Restart VoltronBot for changes to take effect.')

		con.commit()
		con.close()


	def list_modules(self, input, command):
		con, cur = get_db()

		sql = "SELECT * FROM modules"
		cur.execute(sql)
		res = cur.fetchall()

		self.buffer_print('VOLTRON', '')
		self.buffer_print('VOLTRON', 'Available Modules:')

		for r in res:
			mod_str = '  ' + r['module_name']
			if not r['enabled']:
				mod_str += ' (DISABLED)'
			self.buffer_print('VOLTRON', mod_str)

		self.buffer_print('VOLTRON', '')

		con.commit()
		con.close()
