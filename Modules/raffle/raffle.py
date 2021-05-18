from base.module import ModuleBase, ModuleAdminCommand
from base.events import EVT_CHATCOMMAND, EVT_TIMER

import re
import time
import random

import humanize

class RaffleModule(ModuleBase):
	module_name = "raffle"
	DEFAULT_RAFFLE_TIME = 300
	DEFAULT_RAFFLE_COMMAND = 'join'
	DEFAULT_RAFFLE_ALERT_INTERVAL = 60
	DEFAULT_RAFFLE_WINNERS = 1
	def setup(self):
		self._module_data = self.get_module_data()
		self._raffles_active = False
		if not 'raffles' in self._module_data:
			self._module_data['raffles'] = {}
		if not 'active_raffles' in self._module_data:
			self._module_data['active_raffles'] = []
		if not 'last_raffle' in self._module_data:
			self._module_data['last_raffle'] = {}

		if len(self._module_data.get('active_raffles', [])) > 0:
			self._raffles_active = True

		self.register_admin_command(ModuleAdminCommand(
			'new',
			self._new_raffle,
			usage = f'{self.module_name} new <name>',
			description = 'Create a new raffle'
		))

		self.register_admin_command(ModuleAdminCommand(
			'stop',
			self._stop_active_raffle,
			usage = f'{self.module_name} stop <raffle_name>',
			description = 'Stop a running raffle'
		))

		self.register_admin_command(ModuleAdminCommand(
			'list',
			self._list_raffles,
			usage = f'{self.module_name} list',
			description = 'Lists all raffles'
		))

		self.register_admin_command(ModuleAdminCommand(
			'time',
			self._set_time,
			usage = f'{self.module_name} time <raffle_name> <time>',
			description = 'Set how long <raffle_name> lasts in <time> seconds'
		))

		self.register_admin_command(ModuleAdminCommand(
			'command',
			self._set_command,
			usage = f'{self.module_name} time <raffle_name> !<command>',
			description = 'Set the comamnd to join <raffle_name>. Defaults to !join'
		))

		self.register_admin_command(ModuleAdminCommand(
			'interval',
			self._set_interval,
			usage = f'{self.module_name} interval <raffle_name> <interval>',
			description = 'Sets the interval of messages to be posted in chat during an active raffle to <interval> seconds'
		))

		self.register_admin_command(ModuleAdminCommand(
			'prize',
			self._set_prize,
			usage = f'{self.module_name} prize <raffle_name> <prize>',
			description = 'Set the prize for <raffle_name> to <prize>'
		))

		self.register_admin_command(ModuleAdminCommand(
			'winners',
			self._set_winners,
			usage = f'{self.module_name} winners <raffle_name> <winners>',
			description = 'Sets the number of winners of <raffle_name> to <winners>'
		))

		self.register_admin_command(ModuleAdminCommand(
			'confirm',
			self._set_confirm,
			usage = f'{self.module_name} confirm <raffle_name> <on/off>',
			description = 'Turn confirmation messsage on or off when joining a raffle.'
		))

		self.event_listen(EVT_CHATCOMMAND, self.command)
		self.event_listen(EVT_TIMER, self.timer)

	def command(self, event):
		if event.command == 'raffle':
			if event.is_mod:
				self.start_raffle(event)
			return

		if event.command == 'redraw':
			if event.is_broadcaster:
				self.redraw_raffle(event)
			return

		if not self._raffles_active:
			return

		for active in self._module_data.get('active_raffles', []):
			if event.command == active['raffle'].get('command', self.DEFAULT_RAFFLE_COMMAND):
				if event.display_name not in active['entrants']:
					active['entrants'].append(event.display_name)
					if active['raffle'].get('confirm', False):
						self.send_chat_message(f'You have successfully joined the raffle, @{event.display_name}')
				else:
					self.send_chat_message(f'You have already joined, @{event.display_name}')


	def timer(self, event):
		if not self._raffles_active:
			return

		active = self._module_data.get('active_raffles', [])
		to_remove = []
		now = time.time()
		for raffle in active:
			if now >= raffle['end_time']:
				win_chance = '0%'
				if raffle['entrants']:
					win_chance = '%0.2f%%' % ((1/len(raffle['entrants']) * 100))

				self.send_chat_message(f'Raffle {raffle["name"]} has ended! {len(raffle["entrants"])} users entered ({win_chance} chance of winning).')
				self.print(f'Raffle {raffle["name"]} has ended! {len(raffle["entrants"])} users entered ({win_chance} chance of winning).')
				to_remove.append(raffle)
				winners = self.choose_winner(raffle)
				if winners:
					self.send_chat_message(f'Winners: {", ".join(winners)}')
					self.print(f'Winners: {", ".join(winners)}')
				else:
					self.send_chat_message('Nobody entered the raffle :(')
					self.print('Nobody entered the raffle :(')
				continue

			if now >= raffle['next_notif']:
				time_left = int(raffle['end_time'] - now)
				enter_command = raffle.get('command', self.DEFAULT_RAFFLE_COMMAND)
				self.send_chat_message(f'Raffle has {humanize.naturaldelta(time_left)} remaining. Type !{enter_command} to join!')
				raffle['next_notif'] = raffle['raffle']['alert_interval'] + now

		for raffle in to_remove:
			self._module_data['last_raffle'][raffle['name']] = raffle
			self._module_data['active_raffles'].remove(raffle)

		if not self._module_data.get('active_raffles', []):
			self._raffles_active = False

		self.save_module_data(self._module_data)

	def redraw_raffle(self, event):
		if len(event.args) < 1:
			self.send_chat_message(f'Must include raffle name. @{event.display_name}')
			return

		raffle_name = event.args[0]

		if not raffle_name in self._module_data['last_raffle'].keys():
			self.send_chat_message(f'No data for raffle "{raffle_name}". @{event.display_name}')
			return

		old_raffle = self._module_data['last_raffle'][raffle_name]
		new_winners = self.choose_winner(old_raffle)

		if new_winners:
			self.send_chat_message(f'Redraw winners for {raffle_name}: {", ".join(new_winners)}')
			self.print(f'Redraw winners for {raffle_name}: {", ".join(new_winners)}')
		else:
			self.send_chat_message('No more users have entered :(')

		self._module_data['last_raffle'][old_raffle['name']] = old_raffle

	def start_raffle(self, event):
		if len(event.args) < 1:
			self.send_chat_message(f'Must include raffle name. @{event.display_name}')
			return

		raffle_name = event.args[0]
		if not raffle_name in self._module_data['raffles']:
			self.send_chat_message(f'No raffle named "{raffle_name}". @{event.display_name}')
			return

		for active in self._module_data.get('active_raffles', []):
			if active['name'] == raffle_name:
				self.send_chat_message(f'Raffle "{raffle_name}" is already running! @{event.display_name}')
				return

		raffle = self._module_data['raffles'][raffle_name]
		end_time = time.time() + raffle.get('time', self.DEFAULT_RAFFLE_TIME)
		next_notif = time.time() + raffle.get('alert_interval', self.DEFAULT_RAFFLE_ALERT_INTERVAL)

		active_raffle = {
			'raffle': raffle,
			'end_time': end_time,
			'next_notif': next_notif,
			'name': raffle_name,
			'entrants': []
		}

		self._module_data['active_raffles'].append(active_raffle)
		self.save_module_data(self._module_data)
		self._raffles_active = True
		prize = raffle.get('prize')
		enter_command = raffle.get('command', self.DEFAULT_RAFFLE_COMMAND)

		prize_str = ''
		if prize:
			prize_str = f' for {prize}'

		self.send_chat_message(f'Raffle {raffle_name} has started{prize_str}! Type !{enter_command} in chat to enter!')

	def choose_winner(self, active):
		winner_count = active['raffle'].get('winners', self.DEFAULT_RAFFLE_WINNERS)
		entrants = active['entrants']
		winners = []
		count = 0
		while count < winner_count and len(entrants) > 0:
			count += 1
			this_winner = random.choice(entrants)
			winners.append(this_winner)
			entrants.remove(this_winner)

		return winners

	def _new_raffle(self, input, command):
		match = re.search(r'^([^ ]+)$', input.strip())

		if not match:
			self.print(f'Usage: {command.usage}')
			return

		raffle_name = match.group(1).lower()

		if raffle_name in self._module_data['raffles']:
			self.print(f'Raffle "{raffle_name}" already exists')
			return

		self._module_data['raffles'][raffle_name] = {}
		self.print(f'Raffle "{raffle_name}" successfully created!')

	def _stop_active_raffle(self, input, command):
		match = re.search(r'^([^ ]+)$', input.strip())

		if not match:
			self.print(f'Usage: {command.usage}')
			return

		raffle_name = match.group(1).lower()
		active_raffle = None

		for raffle in self._module_data.get('active_raffles', []):
			if raffle['name'] == raffle_name:
				active_raffle = raffle
				break

		if not active_raffle:
			self.print(f'No active raffle named {raffle_name}')
			return

		self._module_data['active_raffles'].remove(active_raffle)
		self.save_module_data(self._module_data)
		self.print(f'Raffle {raffle_name} has been stopped')


	def _list_raffles(self, input, command):
		for raffle in self._module_data['raffles']:
			raffle_data = self._module_data['raffles'][raffle]
			raffle_time = raffle_data.get('time', self.DEFAULT_RAFFLE_TIME)
			raffle_command = raffle_data.get('command', self.DEFAULT_RAFFLE_COMMAND)
			raffle_alert_interval = raffle_data.get('alert_interval', self.DEFAULT_RAFFLE_ALERT_INTERVAL)
			raffle_winners = raffle_data.get('winners', self.DEFAULT_RAFFLE_WINNERS)
			raffle_confirm = raffle_data.get('confirm', False)
			prize = raffle_data.get('prize', 'None')
			self.print(f'{raffle}:')
			self.print(f'  Prize: {prize}')
			self.print(f'  Time: {raffle_time}')
			self.print(f'  Command: !{raffle_command}')
			self.print(f'  Alert Interval: {raffle_alert_interval}')
			self.print(f'  Winners: {raffle_winners}')
			self.print(f'  Confirm: {raffle_confirm}')

	def _set_time(self, input, command):
		params = input.split()
		if not len(params) == 2:
			self.print(f'Usage: {command.usage}')
			return

		if not params[1].isdigit():
			self.print(f'Usage: {command.usage}')
			return

		raffle_name = params[0]
		raffle_time = int(params[1])

		if not raffle_name in self._module_data['raffles']:
			self.print(f'Raffle "{raffle_name}" does not exist')
			return

		self._module_data['raffles'][raffle_name]['time'] = raffle_time
		self.save_module_data(self._module_data)
		self.print(f'Time for "{raffle_name}" set to {raffle_time} seconds')

	def _set_prize(self, input, command):
		match = re.search(r'^([^ ]+)\s(.+)$', input)
		if not match:
			self.print(f'Usage: {command.usage}')
			return

		raffle_name = match.group(1)
		raffle_prize = match.group(2)

		if not raffle_name in self._module_data['raffles']:
			self.print(f'Raffle "{raffle_name}" does not exist')
			return

		self._module_data['raffles'][raffle_name]['prize'] = raffle_prize
		self.save_module_data(self._module_data)
		self.print(f'Prize for {raffle_name} set to {raffle_prize}.')

	def _set_command(self, input, command):
		match = re.search(r'^([^ ]+) !([^ ]+)$', input.strip())

		if not match:
			self.print(f'Usage: {command.usage}')
			return

		raffle_name = match.group(1)
		join_command = match.group(2)

		if not raffle_name in self._module_data['raffles']:
			self.print(f'Raffle "{raffle_name}" does not exist')
			return

		self._module_data['raffles'][raffle_name]['command'] = join_command
		self.save_module_data(self._module_data)
		self.print(f'Command for "{raffle_name}" set to !{join_command}')

	def _set_interval(self, input, command):
		params = input.split()
		if not len(params) == 2:
			self.print(f'Usage: {command.usage}')
			return

		if not params[1].isdigit():
			self.print(f'Usage: {command.usage}')
			return

		raffle_name = params[0]
		raffle_interval = int(params[1])

		if not raffle_name in self._module_data['raffles']:
			self.print(f'Raffle "{raffle_name}" does not exist')
			return

		self._module_data['raffles'][raffle_name]['alert_interval'] = raffle_interval
		self.save_module_data(self._module_data)
		self.print(f'Alert interval for "{raffle_name}" set to {raffle_interval} seconds')

	def _set_winners(self, input, command):
		params = input.split()
		if not len(params) == 2:
			self.print(f'Usage: {command.usage}')
			return

		if not params[1].isdigit():
			self.print(f'Usage: {command.usage}')
			return

		raffle_name = params[0]
		raffle_winners = int(params[1])

		if not raffle_name in self._module_data['raffles']:
			self.print(f'Raffle "{raffle_name}" does not exist')
			return

		if not raffle_winners > 0:
			self.print('Must be at least 1 winner')
			return

		self._module_data['raffles'][raffle_name]['winners'] = raffle_winners
		self.save_module_data(self._module_data)
		self.print(f'There will be {raffle_winners} winners for "{raffle_name}"')

	def _set_confirm(self, input, command):
		match = re.search('^([^ ]+)\s(on|off)$', input)
		if not match:
			self.print(f'Usage: {command.usage}')
			return

		raffle_name = match.group(1)
		confirm = match.group(2) == 'on'

		if not raffle_name in self._module_data['raffles']:
			self.print(f'Raffle "{raffle_name}" does not exist')
			return

		self._module_data['raffles'][raffle_name]['confirm'] = confirm
		self.save_module_data(self._module_data)
		self.print(f'Confirmation messages for {raffle_name} turned {match.group(2)}')


	def shutdown(self):
		self.save_module_data(self._module_data)
