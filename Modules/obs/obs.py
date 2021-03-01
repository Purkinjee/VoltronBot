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

def obs_ws_connect(buffer_queue, host, port, password):
	ws = WebSocket()
	try:
		ws.connect(f'ws://{host}:{port}')

		ws.send(json.dumps({
			"request-type": "GetAuthRequired",
			"message-id": "1"
		}))
		res = json.loads(ws.recv())

		if res['status'] != 'ok':
			buffer_queue.put(('ERR', res['error']))
			return None

		if res.get('authRequired'):
			sec = base64.b64encode(hashlib.sha256((password + res['salt']).encode('utf-8')).digest())
			auth = base64.b64encode(hashlib.sha256(sec + res['challenge'].encode('utf-8')).digest()).decode('utf-8')
			ws.send(json.dumps({"request-type": "Authenticate", "message-id": '2', "auth": auth}))

			res = json.loads(ws.recv())
			if res['status'] != 'ok':
				self.buffer_queue.put(('ERR', res['error']))
				return None

		return ws

	except socket.error as error:
		buffer_queue.put(('ERR', error))
		return None

class OBSThread(threading.Thread):
	def __init__(self, obs_queue, buffer_queue, host, port, password):
		threading.Thread.__init__(self)
		self.obs_queue = obs_queue
		self.buffer_queue = buffer_queue
		self._keep_running = True
		self.errors = False

		self.host = host
		self.port = port
		self.password = password

		self._render_end_times = {}

		self._call_id = 1000

		self._ws = None

	def run(self):
		while self._keep_running:
			event = self.obs_queue.get()

			if isinstance(event, str) and event.lower() == 'shutdown':
				self._keep_running = False
				break

			command = event

			if command.get('action') in ('timedsource', 'timedfilter', 'hidetimedsource', 'hidetimedfilter'):
				self.render_cycle(command)

			elif command.get('action') == 'scenechange':
				self.scene_change(command)

	def scene_change(self, command):
		if 'source_scenes' in command:
			if type(command['source_scenes']) == type(''):
				source_scenes = command['source_scenes'].split()
			else:
				source_scenes = command['source_scenes']

			req = {
				'message-id': self.call_id,
				'request-type': 'GetCurrentScene'
			}

			if self.send_obs_command(req):
				res = {}
				while res.get('message-id', -1) != req['message-id']:
					res = json.loads(self.obs_ws.recv())
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

		self.send_obs_command(req)

	def render_cycle(self, command):
		ident = ""
		args = None
		kwargs = {}
		func = None
		action = command.get('action')
		render_order = (True, False)
		if action in ('timedfilter', 'hidetimedfilter'):
			args = (command['source'], command['filter'])
			kwargs = {}
			func = self.render_filter
			ident = f"timedfilter_{command['source']}_{command['filter']}"
			if action == 'hidetimedfilter':
				render_order = (False, True)
		elif action in ('timedsource', 'hidetimedsource'):
			args = (command['scene'], command['source'])
			kwargs = {}
			func = self.render_source
			ident = f"timedsource_{command['scene']}_{command['source']}"
			if action == 'hidetimedsource':
				render_order = (False, True)

		if func is None:
			return

		render_time = 0
		end_time = self._render_end_times.get(ident, 0)
		if end_time > time.time():
			render_time = (end_time - time.time()) + 0.5

		for render in render_order:
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

	def render_filter(self, source, filter, render=True):
		req = {
			'message-id': self.call_id,
			'request-type': 'SetSourceFilterVisibility',
			'filterName': filter,
			'sourceName': source,
			'filterEnabled': render
		}
		self.send_obs_command(req)

	def render_source(self, scene, source, render=True):
		req = {
			'message-id': self.call_id,
			'request-type': 'SetSceneItemRender',
			'scene-name': scene,
			'source': source,
			'render': render
		}
		self.send_obs_command(req)

	def send_obs_command(self, req):
		try:
			self.obs_ws.send(json.dumps(req))
			return True
		except:
			self.errors = True
			self.buffer_queue.put(('ERR', 'Error connecting to OBS.'))
			self.buffer_queue.put(('ERR', 'Check your settings and make sure OBS is running'))
			return False

	def shutdown(self):
		self._keep_running = False

	def _ws_connect(self):
		if self._ws:
			self._ws.close()

		ws = obs_ws_connect(self.buffer_queue, self.host, self.port, self.password)
		if ws is not None:
			self._ws = ws

	@property
	def obs_ws(self):
		if not self._ws or self.errors:
			self.errors = False
			self._ws_connect()
		return self._ws

	@property
	def call_id(self):
		self._call_id += 1
		return str(self._call_id)

class OBS(ModuleBase):
	module_name = 'obs'
	def setup(self):
		self._obs_data = self.get_module_data()
		self.obs_queue = Queue()
		self.obs_thread = None

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
			usage = f'{self.module_name} add_timed_source !<command>',
			description = 'Adds a command to show a source for a set period of time.',
		))

		self.register_admin_command(ModuleAdminCommand(
			'hide_timed_source',
			self._hide_timed_source,
			usage = f'{self.module_name} hide_timed_source !<command>',
			description = 'Adds a command to hide a source for a set period of time.',
		))

		self.register_admin_command(ModuleAdminCommand(
			'add_timed_filter',
			self._add_timed_filter,
			usage = f'{self.module_name} add_timed_filter !<command> <source>',
			description = 'Adds a command to show a filter for <source> for a set period of time.',
		))

		self.register_admin_command(ModuleAdminCommand(
			'hide_timed_filter',
			self._hide_timed_filter,
			usage = f'{self.module_name} hide_timed_filter !<command> <source>',
			description = 'Adds a command to hide a filter for <source> for a set period of time.',
		))

		self.register_admin_command(ModuleAdminCommand(
			'add_scene_change',
			self._add_scene_change,
			usage = f'{self.module_name} add_scene_change !<command> <scene> <source_scene>...',
			description = 'Adds a command to change to <scene>. Will only function if you are currently on <source> scene if specified. Can list multiple source scenes.',
		))

		self.register_admin_command(ModuleAdminCommand(
			'delete',
			self._delete_command,
			usage = f'{self.module_name} delete !<command>',
			description = 'Delete <!command>',
		))

		self.event_listen(EVT_CHATCOMMAND, self.command)
		self.restart_obs_thread()

	def command(self, event):
		if not event.command in self._obs_data['commands']:
			return False

		command = self._obs_data['commands'][event.command]

		self.obs_queue.put(command)

		self.save_module_data(self._obs_data)

		return True

	def _add_timed_source(self, input, command):
		self._hide_show_timed_source('timedsource', input, command)

	def _hide_timed_source(self, input, command):
		self._hide_show_timed_source('hidetimedsource', input, command)

	def _hide_show_timed_source(self, action, input, command):
		match = re.search(r'^!([^ ]+)$', input)
		if not match:
			self.print(f'Usage: {command.usage}')
			return

		new_command = match.group(1)

		## Callback when scene is selected
		def scene_selected(scene):
			## Callback when source is selected
			def source_selected(source):
				## Callback when user input time
				def time_selected(prompt):
					if prompt.lower() == 'c':
						self.update_status_text()
						return True

					if not prompt.isdigit():
						return False

					## Limit these to 5 minutes which should be more than enough
					seconds = int(prompt)
					if seconds > 300:
						self.print('Max time is 300 seconds')
						return False

					self._obs_data['commands'][new_command] = {
						'action': action,
						'scene': scene,
						'source': source,
						'time':  seconds
					}

					self.save_module_data(self._obs_data)
					self.print(f'Command !{new_command} successfully added')
					self.update_status_text()
					return True


				self.update_status_text('For how many seconds? c to cancel')
				self.prompt_ident = self.get_prompt('Time (s) > ', time_selected)

			self.select_source(source_selected, scene=scene)

		self.select_scene(scene_selected)

	def _add_timed_filter(self, input, command):
		self._add_hide_timed_filter('timedfilter', input, command)

	def _hide_timed_filter(self, input, command):
		self._add_hide_timed_filter('hidetimedfilter', input, command)

	def _add_hide_timed_filter(self, action, input, command):
		match = re.search(r'^!([^ ]+) (.+)$', input)
		if not match:
			self.print(f'Usage: {command.usage}')
			return

		new_command = match.group(1)
		source = match.group(2).strip()

		def filter_selected(filter):
			def time_selected(time):
				if time.lower() == 'c':
					self.update_status_text()
					return True

				if not time.isdigit():
					return False

				seconds = int(time)
				if seconds > 300:
					self.print('Max time is 300 seconds')
					return False

				self._obs_data['commands'][new_command] = {
					'action': action,
					'filter': filter,
					'source': source,
					'time':  seconds
				}

				self.save_module_data(self._obs_data)
				self.update_status_text()
				self.print(f'Command !{new_command} successfully added')
				return True

			self.update_status_text('For how many seconds? c to cancel.')
			self.prompt_ident = self.get_prompt('Time (s) > ', time_selected)

		self.select_source_filter(filter_selected, source)

	def _add_scene_change(self, input, command):
		match = re.search(r'^!([^ ]+)$', input)
		if not match:
			self.print(f'Usage: {command.usage}')
			return

		new_command = match.group(1)
		if new_command in self._obs_data['commands']:
			self.print(f'Command already exists: !{new_command}')
			return

		def scene_selected(scene_name):
			if scene_name is None:
				self.print('Must select target scene')
				self.update_status_text()
				return
			def source_scenes_selected(source_scenes):
				self.print(f'Target Scene: {scene_name}')
				for s in source_scenes:
					self.print(f'Source Scene: {s}')

				self._obs_data['commands'][new_command] = {
					'action': 'scenechange',
					'scene': scene_name
				}
				if None in source_scenes:
					source_scenes.remove(None)
				if source_scenes:
					self._obs_data['commands'][new_command]['source_scenes'] = source_scenes

				self.save_module_data(self._obs_data)

				self.print(f'Command !{new_command} added')
				self.print(f'  Target Scene: {scene_name}')
				if source_scenes:
					self.print('  Source Scenes:')
					for s in source_scenes:
						self.print(f'    - {s}')

				self.update_status_text()

			self.select_scene(source_scenes_selected, multiple=True)
			self.print("Select valid scenes to switch FROM")
			self.print("Multiple can be selected. Separate numbers with spaces.")

		self.select_scene(scene_selected)
		self.print("Select scene to switch TO")


	def _add_scene_change_old(self, input, command):
		match = re.search(r'^!([^ ]+) ([^ ]+) ?(.+)?$', input)
		if not match:
			self.print(f'Usage: {command.usage}')
			return

		command = match.group(1)
		scene = match.group(2)
		from_scene = match.group(3)

		if command in self._obs_data['commands']:
			self.print(f'Command already exists: !{command}')
			return

		self._obs_data['commands'][command] = {
			'action': 'scenechange',
			'scene': scene
		}
		if from_scene:
			self._obs_data['commands'][command]['source_scenes'] = from_scene

		self.save_module_data(self._obs_data)
		self.print(f'Command !{command} successfully added')

	def _delete_command(self, input, command):
		match = re.search(r'^!([^ ]+)$', input)
		if not match:
			self.print(f'Usage: {command.usage}')
			return

		command = match.group(1)
		if command not in self._obs_data['commands']:
			self.print(f'Command !{command} does not exist')
			return

		del self._obs_data['commands'][command]
		self.save_module_data(self._obs_data)
		self.print(f'Command !{command} successfully deleted')

	def _set_host(self, input, command):
		match = re.search('^([^ ]+)$', input)
		if not match:
			self.print(f'Usage: {command.usage}')
			self.print(f'Current host: {self.host}')
			return

		new_host = match.group(1)
		self._obs_data['host'] = new_host
		self.save_module_data(self._obs_data)
		self.print(f'Host set to: {self.host}')
		self.restart_obs_thread()

	def _set_port(self, input, command):
		match = re.search('^(\d+)$', input)
		if not match:
			self.print(f'Usage: {command.usage}')
			self.print(f'Current port: {self.port}')
			return

		new_port = int(match.group(1))
		self._obs_data['port'] = new_port
		self.save_module_data(self._obs_data)
		self.print(f'Port set to: {self.port}')
		self.restart_obs_thread()

	def _set_password(self, input, command):
		match = re.search('^([^ ]+)$', input)
		if not match:
			self.print(f'Usage: {command.usage}')
			return

		new_pw = match.group(1)
		if new_pw.lower() == 'none':
			new_pw = None
		self._obs_data['password'] = new_pw
		self.save_module_data(self._obs_data)
		self.print('Password updated')
		self.restart_obs_thread()

	def _list_obs_commands(self, input, command):
		self.print('')
		self.print(f'Available commands in {self.module_name} module:')
		for command in sorted(self._obs_data['commands']):
			output_str = "  !{command}".format(
				command = command
			)

			self.print(output_str)
		self.print('')

	def _command_details(self, input, command):
		match = re.search(r'^!([^ ]+)$', input)

		if not match:
			self.print(f'Usage: {command.usage}')
			return

		command = match.group(1)
		if not command in self._obs_data['commands']:
			self.print(f'Unknown command: !{command}')
			return

		self.print(f'Details for command !{command}:')

		for key in self._obs_data['commands'][command]:
			if key in ('mod_only', 'broadcaster_only', 'user_cooldown', 'global_cooldown', 'runtime'):
				continue

			self.print(f"  {key}: {self._obs_data['commands'][command][key]}")

	def select_source_filter(self, callback, source):
		obs_ws = obs_ws_connect(self.voltron.buffer_queue, self.host, self.port, self.password)
		req = {
			'message-id': "15",
			'request-type': 'GetSourceFilters',
			'sourceName': source
		}
		filters = []
		if self.send_obs_command(obs_ws, req):
			res = json.loads(obs_ws.recv())
			if res['status'] == 'error':
				self.print(res['error'])
				return None
			if not res['filters']:
				self.print(f'No filters exist for source "{source}"')
				return None
			self.print(f"Filters for {source}:")
			for key in res['filters']:
				filters.append(key['name'])
				self.print(f"  {len(filters)}. {key['name']}")
		else:
			return None

		def filter_selected(filter):
			if filter.lower() == 'c':
				self.update_status_text()
				return True

			if not filter.isdigit():
				return False

			filter = int(filter)
			if filter < 1 or filter > len(filters):
				return False

			callback(filters[filter-1])
			return True

		self.update_status_text('Select a filter. c to cancel')
		self.prompt_ident = self.get_prompt('Filter # > ', filter_selected)

	def select_source(self, callback, scene=None):
		obs_ws = obs_ws_connect(self.voltron.buffer_queue, self.host, self.port, self.password)
		req = {
			'message-id': "10",
			'request-type': 'GetSceneItemList',
			'sceneName': scene
		}
		count = 0
		sources = []
		if self.send_obs_command(obs_ws, req):
			res = json.loads(obs_ws.recv())
			scene_name = scene if scene is not None else 'current'
			self.print(f'Sources for scene "{scene_name}"')
			for key in res['sceneItems']:
				sources.append(key['sourceName'])
				count += 1
				self.print(f"  {count}. {key['sourceName']}")
		else:
			return None

		def scene_selected(source):
			if source.lower() == 'c':
				self.update_status_text()
				return True

			if not source.isdigit():
				return False

			source = int(source)
			if source < 1 or source > count:
				return False

			callback(sources[source-1])
			#self.update_status_text()
			return True


		self.update_status_text('Select a source. c to cancel')
		self.prompt_ident = self.get_prompt('Source # > ', scene_selected)

	def select_scene(self, callback, multiple=False):
		obs_ws = obs_ws_connect(self.voltron.buffer_queue, self.host, self.port, self.password)
		req = {
			'message-id': "10",
			'request-type': 'GetSceneList'
		}
		count = 1
		scenes = []
		if self.send_obs_command(obs_ws, req):
			res = json.loads(obs_ws.recv())
			self.print('Scenes:')
			for key in res['scenes']:
				scenes.append(key['name'])
				self.print(f"  {count}. {key['name']}")
				count += 1
			scenes.append(None)
			self.print(f"  {count}. None")
		else:
			return None

		def scene_selected(scene):
			if scene.lower() == 'c':
				self.update_status_text()
				return True

			if multiple:
				scene_input = scene.split()
			else:
				scene_input = [scene]

			scene_names = []
			for s in scene_input:
				if not s.isdigit():
					self.print(f'Invalid selection: {s}')
					return False

				s = int(s)
				if s < 1 or s > count:
					self.print(f'Invalid selection: {s}')
					return False
				scene_names.append(scenes[s-1])

			if multiple:
				callback(scene_names)
			elif len(scene_names) == 1:
				callback(scene_names[0])

			return True

		if multiple:
			self.update_status_text('Select scenes separated by spaces. c to cancel.')
		else:
			self.update_status_text('Select a scene. c to cancel')
		self.prompt_ident = self.get_prompt('Scene # > ', scene_selected)

	def send_obs_command(self, ws, req):
		try:
			ws.send(json.dumps(req))
			return True
		except:
			self.buffer_print('ERR', 'Error connecting to OBS.')
			self.buffer_print('ERR', 'Check your settings and make sure OBS is running')
			return False

	def restart_obs_thread(self):
		if self.obs_thread:
			self.obs_queue.put('shutdown')
			self.obs_thread.shutdown()
			self.obs_thread.join()

		self.obs_thread = OBSThread(
			self.obs_queue,
			self.voltron.buffer_queue,
			self.host,
			self.port,
			self.password
		)
		self.obs_thread.start()

	def shutdown(self):
		self.obs_queue.put('shutdown')
		self.obs_thread.shutdown()
		self.obs_thread.join()
		self.save_module_data(self._obs_data)

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
