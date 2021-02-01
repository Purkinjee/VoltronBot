import socket
import sys
import time
import re
import signal
import requests
import json
import threading

from lib.common import get_broadcaster
from base.events import ChatCommandEvent, ChatMessageEvent, HostEvent, RaidEvent

import config
from Version import VERSION

class IRCBase:
	"""
	The main class for the Twitch ChatBot.
	This is the main thread and will manage all other threads.
	"""
	def __init__(self, buffer_queue, user, broadcaster):
		## PRODUCTION ##
		########
		## SET FERNET KEY HERE FOR PRODUCTION
		########
		self.__fernet_key = ''

		if hasattr(config, 'FERNET_KEY'):
			self.__fernet_key = config.FERNET_KEY
		self.buffer_queue = buffer_queue
		self.user = user
		self.broadcaster = broadcaster
		#self._ts_print("Starting Voltron Bot")
		#self._ts_print("Press Ctrl-C to exit")
		self.keep_listening = True
		self.reconnecting = False
		self.reconnect_attempts = 0

		## Use these variables to detmine uptime for the bot
		## as well as time the socket has been connected
		self.start_time = time.time()
		self.socket_time = time.time()

		## Set the socket timeout to 1 second until we ensure an active
		## connection with a successful PING/PONG
		self.irc = socket.socket()
		self.irc.settimeout(1)
		#self.connect()

		## Last ping and pong times. Set these to 0 so a ping will be
		## sent immediately after connecting
		self._last_ping = 0
		self._last_pong = 0

		self.channel_map = {}
		#self.join_channels()

		#self._ts_print("Voltron bot is fully operational!")

	def message_received(self, display_name, user_id, is_vip, is_mod, is_broadcaster, message):
		"""
		Called whenever a PRIVMSG is received in twitch chat and successfully parsed

		Args:
			display_name (string): The display name of the sender
			user_id (int): The twitch user ID of the sender
			is_mod (bool): True if sender has moderator role
			is_broadcaster (bool): True if sender is the broadcaster
			message (string): The content of the message
		"""
		## Inherit and override
		pass

	def connect(self):
		"""
		Establishes a socket connection to Twitch IRC servers
		Called when class TwitchIRC class is initialized or when the client disconnects
		"""
		self._ts_print("Connecting...", newline=False)
		try:
			self.irc.connect(('irc.chat.twitch.tv', 6667))
		except:
			self.reconnect_attempts += 1
			reconnect_timeout = 10
			if self.reconnect_attempts > 15:
				reconnect_timeout = 120
			if self.reconnect_attempts > 10:
				reconnect_timeout = 60
			if self.reconnect_attempts > 5:
				reconnect_timeout = 30
			self._ts_print(f"Connection Failed. Retrying in {reconnect_timeout} seconds (Attempt {self.reconnect_attempts})")
			time.sleep(reconnect_timeout)
			self.connect()
			return

		self.irc.send("PASS oauth:{oauth}\r\n".format(oauth=self.user.oauth_tokens.token(self.__fernet_key)).encode())
		self.irc.send("NICK {nick}\r\n".format(nick=self.user.user_name).encode())
		self.irc.send("CAP REQ :twitch.tv/tags twitch.tv/commands\r\n".encode())

		## Update the socket time as we just connected
		self.socket_time = time.time()
		#self._last_ping = time.time()
		#self._last_pong = time.time()
		self._last_ping = 0
		self._last_pong = 0

		## The ping here wasn't functional. I believe the connection wasn't established yet
		## And we were never receiving a pong
		#self._ping()
		self.reconnect_attempts = 0
		self._ts_print("Connected!", ts=False)

	def reconnect(self):
		"""
		Terminates the current socket connection to the Twitch IRC servers and calls connect()
		"""
		self.reconnecting = True
		self._ts_print("Reconnecting...")
		self.irc.shutdown(socket.SHUT_RDWR)
		self.irc.close()

		self.irc = socket.socket()
		self.irc.settimeout(1)

		self.connect()
		self.join_channels()
		self.reconnecting = False

	def join_channels(self):
		"""
		Joins the Twitch IRC channel of the broadcaster
		"""
		self._ts_print("Joining channel #{}...".format(self.broadcaster.user_name), newline=False)
		self.irc.send("JOIN #{channel}\r\n".format(channel=self.broadcaster.user_name).encode())
		self.channel_map[self.broadcaster.user_name] = int(self.broadcaster.twitch_user_id)
		self._ts_print('Joined!', ts=False)

		output_str = "{user} successfully joined #{channel}".format(
			user = self.user.display_name,
			channel = self.broadcaster.user_name
		)
		self.buffer_queue.put(('STATUS', output_str))

	def listen(self):
		"""
		Main loop. Listens for messages on the connected socket.
		Calls _handle_response() when a message is received
		"""
		while self.keep_listening:
			try:
				resp = self.irc.recv(2040)
				if resp:
					self._handle_response(resp.decode())
				else:
					## Empty response means the connection is probably dead
					## call reconnect() just to be sure
					#self._ts_print("Empty response... Checking connnection")
					self._check_alive()
			except socket.timeout:
				## If the connection times out make sure Twitch is still responsive
				self._check_alive()
			except socket.error as e:
				## if self.keep_listening is False, we assume that we are shutting
				## down the client and the connection is intentially closed
				self._ts_print(str(e))
				if self.keep_listening:
					if not self.reconnecting:
						self.reconnect()

	def send_message(self, message, action=False):
		"""
		Sends a message in chat

		Args:
			message (string): The message to be sent
			channel (string): The channel to send the message
			action (bool): If True the message will be sent as an ACTION (/me)
		"""

		## Format message appropaitely if we are sending as an ACTION
		if action:
			message = '\001ACTION {message} \001'.format(message=message)
		self.irc.send(f"PRIVMSG #{self.broadcaster.user_name} :{message}\r\n".encode())

	def _handle_response(self, resp):
		## If Twitch pinged, respond with a pong and record a successful exchange
		if re.search(r"^PING", resp):
			#self._ts_print("PING RECV")
			self._last_ping = time.time()
			self._pong()
			return True

		## If we got a pong, log the time and move on
		if re.search(r"^(:tmi\.twitch\.tv )?PONG", resp):
			#self._ts_print("PONG RECV")
			self._last_pong = time.time()
			# Use default socket timeout since we know connection is alive
			self.irc.settimeout(config.DEFAULT_SOCKET_TIMEOUT)
			return True

		## CHECK AND PARSE CHANNEL MESSAGES
		privmsg_regex = (r'^@([^ ]+) :([^ ]+) PRIVMSG #([^ ]+) :([^\r\n]*)')
		match = re.search(privmsg_regex, resp)
		if match:
			## Data containing badges, emote sets, etc
			twitch_shit = match.group(1)
			user_info = match.group(2)
			channel = match.group(3)
			message = match.group(4)

			broadcaster_id = self.channel_map[channel]

			## Parse the display_name out of twitch_shit
			display_match = re.search(
				r'display-name=([^; ]*)',
				twitch_shit
			)
			display_name = display_match.group(1) if display_match else "Unknown"

			## Parse Twitch user ID out of twitch_shit
			id_match = re.search(
				r'user-id=([0-9]+)',
				twitch_shit
			)
			user_id = id_match.group(1) if id_match else False

			## Determine if the sender was a mod
			mod_match = re.search(
				r'user-type=mod',
				twitch_shit
			)
			is_mod = True if mod_match else False

			is_vip = False
			badge_match = re.search(
				r'badges=([^;]+)',
				twitch_shit
			)
			if badge_match:
				badge_info = badge_match.group(1)
				vip_match = re.search(
					r'vip/\d+',
					badge_info
				)
				if vip_match:
					is_vip = True

			## See if the sender is the same as the logged in broadcaster
			is_broadcaster = int(broadcaster_id) == int(user_id)
			if is_broadcaster:
				is_mod = True

			## See if the broadcaster or a mod sent !ping to check the status
			## of the bot
			test_match = re.search(r'^!ping', message)
			if test_match and (is_broadcaster or is_mod):
				t_str = self._format_seconds(time.time() - self.start_time)
				s_str = self._format_seconds(time.time() - self.socket_time)
				msg = f"VoltronBot {VERSION} has been alive for {t_str}"
				self.send_message(msg, action=True)

			## Remove bullshit ASCI characters that will piss off the database
			escapes = ''.join([chr(char) for char in range(1, 32)])
			table = {}
			for char in range(1, 32):
				table[chr(char)] = None
			m = message.translate(table)

			## Call message_received with all of the data that we parseed out
			## out of the message
			self.message_received(
				display_name,
				user_id,
				is_vip,
				is_mod,
				is_broadcaster,
				m
			)
			#return True

		## Check for hosts
		host_regex = r'^:[^ ]+ PRIVMSG [^ ]+ :([^ ]+) is now hosting you'
		match = re.search(host_regex, resp)
		if match:
			display_name = match.group(1)
			self.handle_host(display_name)
			return True

		usernotice_regex = (r'^@([^ ]+) :([^ ]+) USERNOTICE #([^ ]+)')
		match = re.search(usernotice_regex, resp)
		if match:
			twitch_shit = match.group(1)
			user_info = match.group(2)
			channel = match.group(3)

			if re.search(r'msg-id=raid', twitch_shit):
				display_name = "Unknown"
				display_match = re.search(
					r'display-name=([^; ]*)',
					twitch_shit
				)

				if display_match:
					display_name = display_match.group(1)

				viewer_count_match = re.search('msg-param-viewerCount=(\d+)', twitch_shit)
				viewer_count = 0
				if viewer_count_match:
					viewer_count = int(viewer_count_match.group(1))

				self.handle_raid(display_name, viewer_count)
				return True

		## Otherwise log messages to a text file for now
		#self._log(resp)

	def handle_host(self, display_name):
		pass

	def handle_raid(self, display_name, viewer_count):
		pass

	def _log(self, msg):
		if not config.LOG_IRC_DATA:
			return
		log_file = open(config.IRC_LOG_FILE, "a+")
		msg_list = msg.split("\r\n")
		ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
		for m in msg_list:
			log_file.write("[%s] %s\r\n" % (ts, m))

	def _ts_print(self, message, newline=True, ts=True):
		"""
		Prints a nicely formatted string prefixed by a timestamp

		Args:
			message (string): Message to print
			newline (bool): If False a newline will not be output
			ts (bool): If false no timestamp will print
		"""
		output_str = "({channel}) {message}".format(
			channel = self.user.user_name,
			message = message
		)
		self.buffer_queue.put(('INFO', output_str))
		return
		timestamp = time.strftime("%H:%M", time.localtime())
		if ts:
			formatted = "[%s] %s" % (timestamp, message)
		else:
			formatted = message
		if newline:
			print(formatted)
		else:
			print(formatted, end=" ", flush=True)

	def _pong(self):
		"""
		Send PONG to Twitch
		"""
		self.irc.send("PONG :tmi.twitch.tv\r\n".encode())
		self._last_pong = time.time()
		## Use default socket timeout since we know connection is alive
		self.irc.settimeout(config.DEFAULT_SOCKET_TIMEOUT)
		#self._ts_print("PONG SEND")

	def _ping(self):
		"""
		Send PING to Twitch
		"""
		## Theoretically we should never have to do this
		## But twitch be twitchy
		self.irc.send("PING :tmi.twitch.tv\r\n".encode())
		#self._ts_print("PING SEND")
		self._last_ping = time.time()

	def _check_alive(self):
		"""
		Check if the Twitch connection is active
		Call reconnect() if something is sketchy
		"""
		## If we sent a PING and it's been more than 2 seconds without a PONG
		## assume the connection is dead and reconnect

		## Case for the very first ping sent over a connection where we have no pong time.
		## For this case, use the ping time
		if (time.time() - self._last_ping) > 2 and self._last_pong == 0 and self._last_ping > 0:
			self._ts_print("Ping timed out")
			self.reconnect()
		elif (self._last_ping - self._last_pong) > 2:
			self._ts_print("Ping timed out")
			self.reconnect()
		## If we havent had a successful PING/PONG exchange in the last
		## 400 seconds, initate a PING
		elif (time.time() - self._last_pong) > 400:
			#self._ts_print("Checking connection")
			## Set socket timeout to 1 second because something seems to be off
			self.irc.settimeout(1)
			self._ping()


	def disconnect(self):
		"""
		Disconnect socket from Twitch IRC server
		Socket will be closed and unusable after called
		Only call this when shutting down Voltron Bot
		"""
		self._ts_print("Shutting Down...", newline=False)
		self.keep_listening = False
		self.irc.shutdown(socket.SHUT_RDWR)
		self.irc.close()
		self._ts_print("done", ts=False)

	def _format_seconds(self, seconds):
		formatted = ""
		days = seconds // (60 * 60 * 24)
		if days:
			formatted = formatted + "%01i days " % (days)
		seconds %= (60 * 60 * 24)
		hours = seconds // (60 * 60)
		if hours:
			formatted = formatted + "%01i hours " % (hours)
		seconds %= (60 * 60)
		minutes = seconds // 60
		if minutes:
			formatted = formatted + "%01i minutes " % (minutes)
		seconds %= 60

		return formatted.strip()

class BotIRC(threading.Thread, IRCBase):
	def __init__(self, buffer_queue, user, broadcaster):
		threading.Thread.__init__(self)
		IRCBase.__init__(self, buffer_queue, user, broadcaster)

	def run(self):
		self.connect()
		self.join_channels()
		self.listen()

class BroadcasterIRC(threading.Thread, IRCBase):
	def __init__(self, event_queue, buffer_queue, user, broadcaster):
		threading.Thread.__init__(self)
		IRCBase.__init__(self, buffer_queue, user, broadcaster)
		self.event_queue = event_queue

	def run(self):
		self.connect()
		self.join_channels()
		self.listen()

	def handle_host(self, display_name):
		event = HostEvent(display_name)
		self.event_queue.put(event)

	def handle_raid(self, display_name, viewer_count):
		event = RaidEvent(display_name, viewer_count)
		self.event_queue.put(event)

	def message_received(self, display_name, user_id, is_vip, is_mod, is_broadcaster, message):
		match = re.search(r'^!([^ ]+)(.*)', message)
		if match:
			command = match.group(1)
			args = match.group(2).strip()
			event = ChatCommandEvent(
				command,
				args,
				display_name,
				user_id,
				is_vip,
				is_mod,
				is_broadcaster
			)
			self.event_queue.put(event)
		message_event = ChatMessageEvent(
			message,
			display_name,
			user_id,
			is_vip,
			is_mod,
			is_broadcaster
		)
		self.event_queue.put(message_event)
		#self._ts_print("{name}: {msg}".format(name=display_name, msg=message))
