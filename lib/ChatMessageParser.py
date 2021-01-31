import re
import random
from datetime import datetime, timezone, timedelta

from lib.common import get_broadcaster, get_db

class ChatMessageParser:
	def __init__(self, chat_string, event=None):
		self.variables = {
			'sender': self.sender,
			'uptime': self.uptime,
			'count': self.counter,
			'lastplayed': self.last_played,
			'arg': self.argument,
			'@': self.at,
			'random': self.random,
		}

		self.chat_string = chat_string
		self.event = event
		self._twitch_api = None
		self._broadcaster = None

	def recursive_parse(self, chat_string):
		all_vars = re.findall(r'\{([^ ]+)\}', chat_string)
		vars = []
		[vars.append(x) for x in all_vars if x not in vars]
		parsed_str = chat_string

		for v in vars:
			v_parsed = self.recursive_parse(v)
			split = v_parsed.split(':')
			key = split[0]
			args = split[1:]


			if key in self.variables:
				res = self.variables[key](self.event, *args)
				if res != None:
					parsed_str = parsed_str.replace(f'{{{v_parsed}}}', res)
			elif self.event is not None and hasattr(self.event, key):
				parsed_str = parsed_str.replace(f'{{{v_parsed}}}', str(getattr(self.event, key)))

		return parsed_str

	def parse(self):
		return self.recursive_parse(self.chat_string)

	def sender(self, event, *args):
		if not event:
			return None

		return event.display_name

	def at(self, event, *args):
		at_index = 1
		if len(args) >= 1 and re.search(r'^\d+$', args[0]):
			at_index = int(args[0])

		ats = re.findall(r'(@[^ ]+)', event.message)
		if len(ats) < at_index:
			return ''

		return ats[at_index-1]

	def argument(self, event, *args):
		if len(args) != 1:
			return None

		match = re.search(r'^\d+$', args[0])
		if not match:
			return None

		index = int(args[0])

		words = event.message.split(' ')
		if len(words) < index:
			return ''

		return words[index-1]

	def uptime(self, event, *args):
		if not self.broadcaster:
			return None

		stream_info = self.twitch_api.get_stream(self.broadcaster.twitch_user_id)

		if not stream_info:
			return "0 hours 0 minutes"
			#return None

		started_at = datetime.strptime(stream_info['started_at'], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone(timedelta(0)))
		now = datetime.utcnow().replace(tzinfo=timezone(timedelta(0)))
		secs = (now - started_at).total_seconds()

		hours, rem = divmod(secs, 3600)
		minutes, rem = divmod(rem, 60)

		return f'{hours:.0f} hours {minutes:.0f} minutes'

	def random(self, event, *args):
		start = '1'
		end = '100'

		if len(args) >= 2:
			start = args[0]
			end = args[1]
		elif len(args) >= 1:
			start = args[0]

		if not re.search(r'^\d+$', start):
			start = 1
		if not re.search(r'^\d+$', end):
			end = 100

		return str(random.randrange(int(start), int(end)+1))

	def last_played(self, event, *args):
		if len(args) != 1:
			return None

		if not self.twitch_api:
			return None

		match = re.search('^\@?([^ ]+)$', args[0])
		if not match:
			return ''
		user_name = match.group(1)

		user = self.twitch_api.get_user(user_name)
		if not user:
			return ''

		channel = self.twitch_api.get_channel(user['id'])
		return channel.get('game_name', 'No Game')

	def counter(self, event, *args):
		if len(args) != 1:
			return None

		counter_name = args[0]

		con, cur = get_db()

		sql = "SELECT id, value FROM counters WHERE counter_name = ?"
		cur.execute(sql, (counter_name,))

		res = cur.fetchone()

		count = 1
		if not res:
			sql = "INSERT INTO counters (counter_name, value) VALUES (?, 1)"
			cur.execute(sql, (counter_name, ))
			count = 1
		else:
			count = res['value'] + 1
			sql = "UPDATE counters SET value = ? WHERE id = ?"
			cur.execute(sql, (count, res['id']))

		con.commit()
		con.close()

		return str(count)

	@property
	def twitch_api(self):
		if not self._twitch_api:
			if not self.broadcaster:
				return None
			self._twitch_api = self.broadcaster.twitch_api
		return self._twitch_api

	@property
	def broadcaster(self):
		if not self._broadcaster:
			self._broadcaster = get_broadcaster()
		return self._broadcaster
