from xmlrpc.server import SimpleXMLRPCServer
import threading
import json

from lib.common import get_db

class VoltronXMLRPC:
	def __init__(self):
		pass

	def get_module_list(self):
		con, cur = get_db()

		sql = "SELECT * FROM modules WHERE configurable = 1"
		cur.execute(sql)
		res = cur.fetchall()

		con.close()

		return res

	def get_module_data(self, module):
		con, cur = get_db()

		sql = "SELECT data FROM module_data WHERE module_name = ?"
		cur.execute(sql, (module, ))
		res = cur.fetchone()
		con.close()

		module_data = res.get('data', {})

		return module_data

class VoltronXMLRPCThread(threading.Thread):
	def __init__(self):
		threading.Thread.__init__(self)

		xmlrpc = VoltronXMLRPC()
		self.server = SimpleXMLRPCServer(('localhost', 8990), logRequests=False)
		self.server.register_instance(xmlrpc)

	def run(self):
		self.server.serve_forever()

	def shutdown(self):
		self.server.shutdown()
		self.server.server_close()
