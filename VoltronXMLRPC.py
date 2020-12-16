from xmlrpc.server import SimpleXMLRPCServer
import threading
import json
import yaml

from lib.common import get_db

class VoltronXMLRPC:
	def __init__(self, ui):
		self.ui = ui

	def get_module_list(self):
		con, cur = get_db()

		sql = "SELECT * FROM modules WHERE configurable = 1 ORDER BY module_name"
		cur.execute(sql)
		res = cur.fetchall()

		con.close()

		return res

	def execute_command(self, command):
		self.ui.execute_command(command)
		return True

	def get_module_webview(self, module_name):
		webview =  yaml.safe_load(open('CoreModules/account/configuration.yml'))
		module_data = self.get_module_data(module_name)
		data = {'webview': webview, 'module_data': module_data}
		return data

	def get_module_data(self, module):
		con, cur = get_db()

		if module == 'account':
			sql = "SELECT id, user_name, display_name, twitch_user_id, is_broadcaster, is_default FROM oauth ORDER BY is_broadcaster DESC, is_default DESC"
			cur.execute(sql)
			res = cur.fetchall()
			con.close()
			return {'accounts': res}

		sql = "SELECT data FROM module_data WHERE module_name = ?"
		cur.execute(sql, (module, ))
		res = cur.fetchone()
		con.close()

		if not res:
			return {}

		module_data = res.get('data', {})

		return module_data

class VoltronXMLRPCThread(threading.Thread):
	def __init__(self, ui):
		threading.Thread.__init__(self)

		xmlrpc = VoltronXMLRPC(ui)
		self.server = SimpleXMLRPCServer(('127.0.0.1', 8990), logRequests=False)
		self.server.register_instance(xmlrpc)

	def run(self):
		self.server.serve_forever()

	def shutdown(self):
		self.server.shutdown()
		self.server.server_close()
