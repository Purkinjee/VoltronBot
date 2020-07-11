#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import signal
import threading
import time
import sys

from TwitchIRC import TwitchIRC

THREADS = []

class BotExample(TwitchIRC):
	def message_received(self, display_name, user_id, is_mod, is_broadcaster, message):
		print("%s: %s" % (display_name, message))

if __name__ == "__main__":
	bot = BotExample()
	thread = threading.Thread(target=bot.listen)
	thread.start()

	def Exit(signal, frame):
		bot.disconnect()
		thread.join()
		sys.exit()

	signal.signal(signal.SIGINT, Exit)

	while True:
		time.sleep(0.5)
