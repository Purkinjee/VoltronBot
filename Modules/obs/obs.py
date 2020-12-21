from base.module import ModuleBase, ModuleAdminCommand
from websocket import WebSocket
import socket
from base.events import EVT_CHATCOMMAND

import re
import json
import base64
import hashlib
import time
import threading
from queue import Queue

class OBSThread(threading.Thread):
	def __init__(self, obs_queue, buffer_queue):
		threading.Thread.__init__(self)
		self.obs_queue = obs_queue
		self.buffer_queue = buffer_queue
		self._keep_running = True
		self.errors = False

		self._render_end_times = {}

		self._call_id = 1000

	def run(self):
		while self._keep_running:
			event = self.obs_queue.get()

			if isinstance(event, str) and event.lower() == 'shutdown':
				self._keep_running = False
				break

			if len(event) != 2:
				continue

			command = event[0]
			ws = event[1]

			if command.get('action') in ('timedsource', 'timedfilter'):
				self.render_cycle(ws, command)

			elif command.get('action') == 'scenechange':
				self.scene_change(ws, command)

	def scene_change(self, ws, command):
		if 'source_scenes' in command:
			source_scenes = command['source_scenes'].split()

			req = {
				'message-id': self.call_id,
				'request-type': 'GetCurrentScene'
			}

			if self.send_obs_command(ws, req):
				res = {}
				while res.get('message-id', -1) != req['message-id']:
					res = json.loads(ws.recv())
				current_scene = res['name']
				if not current_scene in source_scenes:
					return
			else:
				return

		req = {
			'message-id': self.call_id,
			'request-type': 'SetCurrentScene',
			'scene-name': command['scene']
		}

		self.send_obs_command(ws, req)


	def render_cycle(self, ws, command):
		ident = ""
		args = None
		kwargs = {}
		func = None
		action = command.get('action')
		if action == 'timedfilter':
			args = (ws, command['source'], command['filter'])
			kwargs = {}
			func = self.render_filter
			ident = f"timedfilter_{command['source']}_{command['filter']}"
		elif action == 'timedsource':
			args = (ws, command['scene'], command['source'])
			kwargs = {}
			func = self.render_source
			ident = f"timedsource_{command['scene']}_{command['source']}"


		if func is None:
			return

		render_time = 0
		end_time = self._render_end_times.get(ident, 0)
		if end_time > time.time():
			render_time = (end_time - time.time()) + 0.5

		for render in (True, False):
			kwargs_copy = kwargs.copy()
			kwargs_copy['render'] = render
			t = threading.Thread(
				target=self._delayed_func_call,
				args=(
					render_time,
					func,
					args,
					kwargs_copy
				)
			)
			t.start()
			render_time += int(command['time'])

		self._render_end_times[ident] = time.time() + render_time - int(command['time'])


	def _delayed_func_call(self, delay, func, args, kwargs):
		time.sleep(delay)
		func(*args, **kwargs)

	def render_filter(self, ws, source, filter, render=True):
		req = {
			'message-id': self.call_id,
			'request-type': 'SetSourceFilterVisibility',
			'filterName': filter,
			'sourceName': source,
			'filterEnabled': render
		}
		self.send_obs_command(ws, req)

	def render_source(self, ws, scene, source, render=True):
		req = {
			'message-id': self.call_id,
			'request-type': 'SetSceneItemRender',
			'scene-name': scene,
			'source': source,
			'render': render
		}
		self.send_obs_command(ws, req)

	def send_obs_command(self, ws, req):
		try:
			ws.send(json.dumps(req))
			return True
		except:
			self.errors = True
			self.buffer_queue.put(('ERR', 'Error connecting to OBS.'))
			self.buffer_queue.put(('ERR', 'Check your settings and make sure OBS is running'))
			return False

	def shutdown(self):
		self._keep_running = False

	@property
	def call_id(self):
		self._call_id += 1
		return str(self._call_id)

class OBS(ModuleBase):
	module_name = 'obs'
	def setup(self):
		self._obs_data = self.get_module_data()
		self.obs_queue = Queue()
		self.obs_thread = OBSThread(self.obs_queue, self.voltron.buffer_queue)

		if not 'commands' in self._obs_data:
			self._obs_data['commands'] = {}

		self._call_id = 0

		self._ws = None

		self.register_admin_command(ModuleAdminCommand(
			'host',
			self._set_host,
			usage = f'{self.module_name} host <host>',
			description = 'Sets host for obs websocket. Default is localhost',
		))

		self.register_admin_command(ModuleAdminCommand(
			'port',
			self._set_port,
			usage = f'{self.module_name} port <port>',
			description = 'Sets port for obs websocket. Default is 4444',
		))

		self.register_admin_command(ModuleAdminCommand(
			'password',
			self._set_password,
			usage = f'{self.module_name} password <password>',
			description = 'Sets password for obs websocket. Set to none to clear password.',
		))

		self.register_admin_command(ModuleAdminCommand(
			'list',
			self._list_obs_commands,
			usage = f'{self.module_name} list',
			description = 'List all obs commands'
		))

		self.register_admin_command(ModuleAdminCommand(
			'details',
			self._command_details,
			usage = f'{self.module_name} details !<command>',
			description = 'Show details of !<command>'
		))

		self.register_admin_command(ModuleAdminCommand(
			'add_timed_source',
			self._add_timed_source,
			usage = f'{self.module_name} add_timed_source !<command> <scene> <source> <time>',
			description = 'Adds a command to show <source> in <scene> for <time> seconds. Can use "current" for <scene>.',
		))

		self.register_admin_command(ModuleAdminCommand(
			'add_timed_filter',
			self._add_timed_filter,
			usage = f'{self.module_name} add_timed_filter !<command> <source> <filter> <time>',
			description = 'Adds a command to show <filter> for <source> for <time> seconds.',
		))

		self.register_admin_command(ModuleAdminCommand(
			'add_scene_change',
			self._add_scene_change,
			usage = f'{self.module_name} add_scene_change !<command> <scene> <source_scene>...',
			description = 'Adds a command to change to <scene>. Will only function if you are currently on <source> scene if specified. Can list multiple source scenes.',
		))

		self.register_admin_command(ModuleAdminCommand(
			'mod_only',
			self._toggle_mod_only,
			usage = f'{self.module_name} mod_only !<command>',
			description = 'Toggle mod only permission for command'
		))

		self.register_admin_command(ModuleAdminCommand(
			'broadcaster_only',
			self._toggle_broadcaster_only,
			usage = f'{self.module_name} broadcaster_only !<command>',
			description = 'Toggle broadcaster only permission for command'
		))

		self.register_admin_command(ModuleAdminCommand(
			'delete',
			self._delete_command,
			usage = f'{self.module_name} delete !<command>',
			description = 'Delete <!command>',
		))

		self.event_listen(EVT_CHATCOMMAND, self.command)
		self.obs_thread.start()

	def command(self, event):
		if not event.command in self._obs_data['commands']:
			return False

		command = self._obs_data['commands'][event.command]

		if command.get('broadcaster_only', False) and not event.is_broadcaster:
			return False
		if command.get('mod_only', False) and not event.is_mod:
			return False

		self.obs_queue.put((command, self.obs_ws))

		self.save_module_data(self._obs_data)

		return True

	def _add_timed_source(self, input, command):
		match = re.search(r'^!([^ ]+) ([^ ]+) ([^ ]+) (\d+)$', input)
		if not match:
			self.buffer_print('VOLTRON', f'Usage: {command.usage}')
			return

		command = match.group(1)
		scene = match.group(2)
		source = match.group(3)
		seconds = int(match.group(4))

		if scene.lower() == 'current':
			scene = None

		if command in self._obs_data['commands']:
			self.buffer_print('VOLTRON', f'Command already exists: !{command}')
			return

		self._obs_data['commands'][command] = {
			'action': 'timedsource',
			'scene': scene,
			'source': source,
			'time':  seconds
		}

		self.save_module_data(self._obs_data)
		self.buffer_print('VOLTRON', f'Command !{command} successfully added')

	def _add_timed_filter(self, input, command):
		match = re.search(r'^!([^ ]+) ([^ ]+) ([^ ]+) (\d+)$', input)
		if not match:
			self.buffer_print('VOLTRON', f'Usage: {command.usage}')
			return

		command = match.group(1)
		source = match.group(2)
		filter = match.group(3)
		seconds = int(match.group(4))

		if command in self._obs_data['commands']:
			self.buffer_print('VOLTRON', f'Command already exists: !{command}')
			return

		self._obs_data['commands'][command] = {
			'action': 'timedfilter',
			'filter': filter,
			'source': source,
			'time':  seconds
		}

		self.save_module_data(self._obs_data)
		self.buffer_print('VOLTRON', f'Command !{command} successfully added')

	def _add_scene_change(self, input, command):
		match = re.search(r'^!([^ ]+) ([^ ]+) ?(.+)?$', input)
		if not match:
			self.buffer_print('VOLTRON', f'Usage: {command.usage}')
			return

		command = match.group(1)
		scene = match.group(2)
		from_scene = match.group(3)

		if command in self._obs_data['commands']:
			self.buffer_print('VOLTRON', f'Command already exists: !{command}')
			return

		self._obs_data['commands'][command] = {
			'action': 'scenechange',
			'scene': scene
		}
		if from_scene:
			self._obs_data['commands'][command]['source_scenes'] = from_scene

		self.save_module_data(self._obs_data)
		self.buffer_print('VOLTRON', f'Command !{command} successfully added')

	def _delete_command(self, input, command):
		match = re.search(r'^!([^ ]+)$', input)
		if not match:
			self.buffer_print('VOLTRON', f'Usage: {command.usage}')
			return

		command = match.group(1)
		if command not in self._obs_data['commands']:
			self.buffer_print('VOLTRON', f'Command !{command} does not exist')
			return

		del self._obs_data['commands'][command]
		self.save_module_data(self._obs_data)
		self.buffer_print('VOLTRON', f'Command !{command} successfully deleted')

	def _set_host(self, input, command):
		match = re.search('^([^ ]+)$', input)
		if not match:
			self.buffer_print('VOLTRON', f'Usage: {command.usage}')
			self.buffer_print('VOLTRON', f'Current host: {self.host}')
			return

		new_host = match.group(1)
		self._obs_data['host'] = new_host
		self.save_module_data(self._obs_data)
		self.buffer_print('VOLTRON', f'Host set to: {self.host}')
		self._ws_connect()

	def _set_port(self, input, command):
		match = re.search('^(\d+)$', input)
		if not match:
			self.buffer_print('VOLTRON', f'Usage: {command.usage}')
			self.buffer_print('VOLTRON', f'Current port: {self.port}')
			return

		new_port = int(match.group(1))
		self._obs_data['port'] = new_port
		self.save_module_data(self._obs_data)
		self.buffer_print('VOLTRON', f'Port set to: {self.port}')
		self._ws_connect()

	def _set_password(self, input, command):
		match = re.search('^([^ ]+)$', input)
		if not match:
			self.buffer_print('VOLTRON', f'Usage: {command.usage}')
			return

		new_pw = match.group(1)
		if new_pw.lower() == 'none':
			new_pw = None
		self._obs_data['password'] = new_pw
		self.save_module_data(self._obs_data)
		self.buffer_print('VOLTRON', 'Password updated')
		self._ws_connect()

	def _list_obs_commands(self, input, command):
		self.buffer_print('VOLTRON', '')
		self.buffer_print('VOLTRON', f'Available commands in {self.module_name} module:')
		for command in sorted(self._obs_data['commands']):
			output_str = "  !{command}".format(
				command = command
			)
			if self._obs_data['commands'][command].get('broadcaster_only', False):
				output_str += ' (broadcaster only)'
			if self._obs_data['commands'][command].get('mod_only', False):
				output_str += ' (mod only)'

			self.buffer_print('VOLTRON', output_str)
		self.buffer_print('VOLTRON', '')

	def _command_details(self, input, command):
		match = re.search(r'^!([^ ]+)$', input)

		if not match:
			self.buffer_print('VOLTRON', f'Usage: {command.usage}')
			return

		command = match.group(1)
		if not command in self._obs_data['commands']:
			self.buffer_print('VOLTRON', f'Unknown command: !{command}')
			return

		mod_only = self._obs_data['commands'][command].get('mod_only', False)
		broadcaster_only = self._obs_data['commands'][command].get('broadcaster_only', False)

		self.buffer_print('VOLTRON', f'Details for command !{command}:')
		self.buffer_print('VOLTRON', f'  Mod Only: {mod_only}')
		self.buffer_print('VOLTRON', f'  Broadcaster Only: {broadcaster_only}')

		for key in self._obs_data['commands'][command]:
			if key in ('mod_only', 'broadcaster_only', 'user_cooldown', 'global_cooldown', 'runtime'):
				continue

			self.buffer_print('VOLTRON', f"  {key}: {self._obs_data['commands'][command][key]}")


	def _toggle_mod_only(self, input, command):
		match = re.search(r'^!([^ ]+)$', input)
		if not match:
			self.buffer_print('VOLTRON', f'Usage: {command.usage}')
			return

		command = match.group(1)
		if not command in self._obs_data['commands']:
			self.buffer_print('VOLTRON', f'Command !{command} does not exist')
			return

		mod_only = self._obs_data['commands'][command].get('mod_only', False)

		mod_only = not mod_only
		self._obs_data['commands'][command]['mod_only'] = mod_only
		self.save_module_data(self._obs_data)

		self.buffer_print('VOLTRON', f'Permission changed for !{command} (mod_only={mod_only})')

	def _toggle_broadcaster_only(self, input, command):
		match = re.search(r'^!([^ ]+)$', input)
		if not match:
			self.buffer_print('VOLTRON', f'Usage: {command.usage}')
			return

		command = match.group(1)
		if not command in self._obs_data['commands']:
			self.buffer_print('VOLTRON', f'Command !{command} does not exist')
			return

		broadcaster_only = self._obs_data['commands'][command].get('broadcaster_only', False)

		broadcaster_only = not broadcaster_only
		self._obs_data['commands'][command]['broadcaster_only'] = broadcaster_only
		self.save_module_data(self._obs_data)

		self.buffer_print('VOLTRON', f'Permission changed for !{command} (broadcaster_only={broadcaster_only})')

	def _ws_connect(self):
		if self._ws:
			self._ws.close()

		self._ws = WebSocket()
		try:
			self._ws.connect(f'ws://{self.host}:{self.port}')

			self._ws.send(json.dumps({
				"request-type": "GetAuthRequired",
				"message-id": str(self.call_id)
			}))
			res = json.loads(self._ws.recv())

			if res['status'] != 'ok':
				self.buffer_print('ERR', res['error'])
				self._ws = None
				return

			if res.get('authRequired'):
				sec = base64.b64encode(hashlib.sha256((self.password + res['salt']).encode('utf-8')).digest())
				auth = base64.b64encode(hashlib.sha256(sec + res['challenge'].encode('utf-8')).digest()).decode('utf-8')
				self._ws.send(json.dumps({"request-type": "Authenticate", "message-id": str(self.call_id), "auth": auth}))

				res = json.loads(self._ws.recv())
				if res['status'] != 'ok':
					self.buffer_print('ERR', res['error'])
					self._ws = None
					return
		except socket.error as error:
			self.buffer_print('ERR', error)

	def shutdown(self):
		self.obs_queue.put('shutdown')
		self.obs_thread.shutdown()
		self.obs_thread.join()
		self.save_module_data(self._obs_data)

	@property
	def obs_ws(self):
		if not self._ws or self.obs_thread.errors:
			self.obs_thread.errors = False
			self._ws_connect()
		return self._ws

	@property
	def host(self):
		return self._obs_data.get('host', 'localhost')
	@property
	def port(self):
		return self._obs_data.get('port', 4444)
	@property
	def password(self):
		return self._obs_data.get('password', None)

	@property
	def call_id(self):
		self._call_id += 1
		return self._call_id
