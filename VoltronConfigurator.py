#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import webview
from xmlrpc.client import ServerProxy


class Api:
	def init(self):
		self.xmlrpc = ServerProxy('http://127.0.0.1:8990')
		return None

	def get_module_list(self):
		modules = self.xmlrpc.get_module_list()
		return modules

	def execute_command(self, command):
		self.xmlrpc.execute_command(command)

	def get_module_webview(self, module_name):
		return self.xmlrpc.get_module_webview(module_name)

if __name__ == '__main__':
	api = Api()
	webview.create_window('Voltron Configuration Tool', 'WebviewAssets/index.html', js_api=api, min_size=(600, 500))
	webview.start(debug=True)
