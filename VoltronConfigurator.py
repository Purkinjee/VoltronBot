#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import webview
from xmlrpc.client import ServerProxy


class Api:
	def init(self):
		self.xmlrpc = ServerProxy('http://localhost:8990')

	def get_module_list(self):
		modules = self.xmlrpc.get_module_list()
		return modules

if __name__ == '__main__':
	api = Api()
	webview.create_window('Voltron Configuration Tool', 'WebviewAssets/index.html', js_api=api, min_size=(600, 500))
	webview.start(debug=True)
