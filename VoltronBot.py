#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import signal
import threading
import time
import sys
import queue
import os
import json
from importlib import import_module

from lib.TwitchIRC import BroadcasterIRC, BotIRC
from VoltronUI import VoltronUI
from CoreModules.account import VoltronModule as Account
from lib.common import get_broadcaster, get_all_acccounts, get_db
from lib.eventloop import EventLoop

THREADS = []

class VoltronBot:
	"""
	This is the main class for VoltronBot.
	All instanced classes and threads are managed in this class.
	"""
	def __init__(self):
		self.buffer_queue = queue.Queue()
		self.event_queue = queue.Queue()

		self.irc_map = {}
		self.users = []

		## The object controlling all UI elements
		self.ui = VoltronUI(self.buffer_queue)

		self.event_loop = None
		self.default_account = None

		self.reset()

	def register_module(self, module):
		"""
		This method is automatically called when a module is successfully initialized.
		"""
		self.ui.register_module(module)

	def reset(self):
		"""
		Disconnect and reconnect all IRC connections
		"""
		self.stop()
		users = get_all_acccounts()
		broadcaster = get_broadcaster()

		## If no broadcaster exists the bot is not functional
		if not broadcaster:
			self.buffer_queue.put(('VOLTRON', 'No broadcaster account exists'))
			self.buffer_queue.put(('VOLTRON', "Please add one using 'account add'"))
			self.buffer_queue.put(('VOLTRON', "Or select an existing account using 'account broadcaster'"))
			return
		for user in users:
			if user.is_default:
				self.default_account = user

			## Create a BroadcasterIRC instance for the broadcaster account
			## This instance is responsible for events being added to event_queue
			if user.id == broadcaster.id:
				irc = BroadcasterIRC(self.event_queue, self.buffer_queue, user, broadcaster)
			else:
				irc = BotIRC(self.buffer_queue, user, broadcaster)
			self.irc_map[user.twitch_user_id] = irc
		self.users = users

	def start(self):
		"""
		Start the bot
		"""
		## Start the IRC threads
		for twitch_id in self.irc_map:
			self.irc_map[twitch_id].start()

		## Create the event loop thread and start it
		self.event_loop = EventLoop(self, self.buffer_queue, self.event_queue)
		self.event_loop.start()

	def get_module_data(self, module):
		"""
		Get data saved in the DB for the specified module.

		Args:
			module (instance): The instance of the module object
		"""
		con, cur = get_db()

		sql = "SELECT data FROM module_data WHERE module_name = ?"
		cur.execute(sql, (module.module_name, ))
		res = cur.fetchone()

		con.commit()
		con.close()

		if res:
			return json.loads(res['data'])
		else:
			return {}

	def save_module_data(self, module, data):
		"""
		Save data to the DB for the specified module.

		Args:
			module (instance): The instance of the module object
			data (dict): Module data to be saved
		"""
		con, cur = get_db()

		data_str = json.dumps(data)

		sql = "REPLACE INTO module_data (module_name, data) VALUES (?, ?)"
		cur.execute(sql, (module.module_name, data_str))

		con.commit()
		con.close()

	def send_chat_message(self, message, twitch_id=None):
		"""
		Send a message to IRC using the default account
		Args:
			message (string): Message to be sent
		"""
		if twitch_id and twitch_id in self.irc_map:
			self.irc_map[twitch_id].send_message(message)
		else:
			self.irc_map[self.default_account.twitch_user_id].send_message(message)

	def stop(self):
		"""
		Stop the bot and exit
		"""
		if self.event_loop:
			self.event_queue.put('SHUTDOWN')
			self.event_loop.join()
		for twitch_id in self.irc_map:
			self.irc_map[twitch_id].disconnect()
			self.irc_map[twitch_id].join()
		self.irc_map = {}

if __name__ == "__main__":
	vb = VoltronBot()
	vb.start()

	def Exit(signal, frame):
		vb.stop()
		sys.exit()

	signal.signal(signal.SIGINT, Exit)

	vb.ui.run()
	Exit(None, None)
