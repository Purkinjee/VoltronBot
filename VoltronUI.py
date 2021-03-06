from prompt_toolkit.buffer import Buffer
from prompt_toolkit.document import Document
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.widgets import TextArea
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.containers import HSplit, Window, VSplit
from prompt_toolkit.styles import Style
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit import Application
from prompt_toolkit.lexers import PygmentsLexer
from prompt_toolkit.completion import NestedCompleter, Completer, Completion
from prompt_toolkit.key_binding.bindings.scroll import scroll_one_line_up, scroll_one_line_down
from prompt_toolkit.application import get_app

from pygments.lexer import RegexLexer, bygroups
from pygments import token

import threading
import queue
import re
from uuid import uuid4
import time
from Version import VERSION
import config

DEFAULT_STATUS = 'Ready'
DEFAULT_PROMPT = 'VoltronBot>'

class UIBufferQueue(threading.Thread):
	"""
	This thread watches the buffer queue and outputs data into the main window of the UI
	"""
	def __init__(self, voltron, input_queue, scrolling_output):
		threading.Thread.__init__(self)

		self.input_queue = input_queue
		self.scrolling_output = scrolling_output
		self.voltron = voltron

		self.keep_listening = True

		self.log_levels = ['VOLTRON', 'MODULE', 'CRIT', 'ERR', 'WARN', 'STATUS', 'INFO', 'DEBUG']

	def run(self):
		while self.keep_listening:
			try:
				input = self.input_queue.get()
				## Exit the thread if SHUTDOWN in queue
				if input == 'SHUTDOWN':
					self.keep_listening = False
					break

				if type(input) is tuple and input[0] in self.log_levels:
					if config.LOG_LEVEL in self.log_levels and self.log_levels.index(input[0]) > self.log_levels.index(config.LOG_LEVEL):
						continue
					self.update_scrolling_output(input)
				#if type(input) is tuple and input[0] in ['VOLTRON']:
				#	self.update_scrolling_output(input)
			except queue.Empty:
				pass

	def update_scrolling_output(self, input):
		"""
		Add new text to the main output buffer.

		Args:
			input (tuple): First element is the message type, second is the text to output
		"""
		timestamp = time.strftime("%H:%M", time.localtime())
		extra = ""
		if input[0] == 'MODULE' and len(input) > 2:
			output_str = str(input[2])
			#extra = "<MODULE> "
			tag = str(input[1]).upper()
		else:
			output_str = str(input[1])
			tag = str(input[0])

		new = output_str.replace('\n', '\n[{ts}] {extra}<{tag}> '.format(
			ts = timestamp,
			extra = extra,
			tag = tag
		))
		## Add formated text to buffer and scroll to bottom
		text = "{existing}\n[{ts}] {extra}<{type}> {new}".format(
			existing = self.scrolling_output.text,
			ts = timestamp,
			extra = extra,
			type = tag,
			new = new
		)
		#pos = None
		if not self.voltron._scrolled_to_bottom:
			pos = self.scrolling_output.buffer.document.cursor_position
		else:
			pos = len(text)
		self.scrolling_output.buffer.document = Document(
			text = text,
			#cursor_position = len(text)
			cursor_position = pos
		)

class VoltronOutputLexer(RegexLexer):
	"""
	Lexer for output in the main buffer
	"""
	name = 'Voltron'
	aliases = ['voltron']
	filenames = ['*.vtn']

	tokens = {
		'root': [
			(r'^(\[.*\]\s)(\<WELCOME\>\s)(First message:\s)([^ ]+)(\s\(Not Following\))', bygroups(
				token.Name.Attribute,
				token.Name.Variable,
				token.Text,
				token.Name.Decorator,
				token.Name.Exception
			)),
			(r'^(\[.*\]\s)(\<WELCOME\>\s)(First message:\s)([^ ]+)', bygroups(
				token.Name.Attribute,
				token.Name.Variable,
				token.Text,
				token.Name.Decorator
			)),

			(r'^(\[.+\]\s)(\<VOLTRON\>)', bygroups(token.Name.Attribute, token.Name.Variable)),
			(r'^(\[.+\]\s)(<INFO\>.*)$', bygroups(token.Name.Attribute, token.Name.Attribute)),
			(r'^(\[.+\]\s)(<STATUS>.*)$', bygroups(token.Name.Attribute, token.Name.Label)),
			(r'^(\[.+\]\s)(<ERR>.*)$', bygroups(token.Name.Attribute, token.Name.Exception)),
			(r'^(\[.+\]\s)(\<[^ ]+\>)', bygroups(token.Name.Attribute, token.Name.Variable)),
		]
	}

class VoltronUI:
	"""
	Class that manages all UI elements
	"""
	def __init__(self, buffer_queue):
		self.buffer = Buffer()
		self.modules = {}
		self.module_prompt_callback = None
		self.prompt_ident = None
		self.prompt_ident_skip = []

		key_bindings = KeyBindings()

		default_text = """
Welcome to VoltronBot!
Type ? for available commands.
Control-C or type 'quit' to exit
"""
		lexer = PygmentsLexer(VoltronOutputLexer)
		## Main output TextArea
		self.scrolling_output = TextArea(
			focusable = True,
			text = default_text,
			lexer = lexer
		)

		self.buffer_queue = buffer_queue
		self.buffer_thread = UIBufferQueue(self, self.buffer_queue, self.scrolling_output)
		self.buffer_thread.start()
		self.prompt_queue = queue.Queue()

		## Exit keybinds
		@key_bindings.add('c-q')
		@key_bindings.add('c-c')
		def _exit(event):
			self.buffer_queue.put('SHUTDOWN')
			self.buffer_thread.join()
			event.app.exit()

		## TextArea for prompt
		self.prompt = TextArea(
			height=1,
			#prompt=DEFAULT_PROMPT,
			multiline=False,
			wrap_lines=True
		)
		self.prompt.accept_handler = self.input_recv

		## Create status bar
		self.status_text = FormattedTextControl(text=DEFAULT_STATUS)
		self.scroll_text = FormattedTextControl(text="")

		self.status_window =  Window(
			content=self.status_text,
			height=1,
			style="class:status-bar"
		)
		self.scroll_window = Window(
			content=self.scroll_text,
			height=1,
			width=6,
			style="class:status-bar"
		)
		status_split = VSplit([
			self.status_window,
			self.scroll_window
		])

		self.prompt_text = FormattedTextControl(text=DEFAULT_PROMPT)
		self.prompt_window = Window(content=self.prompt_text, height=1, width=len(DEFAULT_PROMPT)+1)

		## Create top bar
		self.main_container = HSplit([
			Window(content=FormattedTextControl(
				text=f"VoltronBot v{VERSION}"
			), height=1, style="class:title-bar"),

			self.scrolling_output,

			status_split,

			VSplit([
				self.prompt_window,
				self.prompt
			]),
		])

		style = Style([
			('title-bar', 'bg:ansiblue #000000'),
			('status-bar', 'bg:ansicyan #000000'),
			('status-bar-important', 'bg:ansired #000000'),
		])

		self.layout = Layout(self.main_container, focused_element=self.prompt)

		## Keybind for page up
		@key_bindings.add('pageup')
		def _scroll_up(event):
			self.layout.focus(self.scrolling_output)
			scroll_one_line_up(event)
			self.layout.focus(self.prompt)

			if not self._scrolled_to_bottom:
				self.scroll_text.text = '(more)'
			else:
				self.scroll_text.text = ''

		## Keybind for page down
		@key_bindings.add('pagedown')
		def _scroll_down(event):
			self.layout.focus(self.scrolling_output)
			scroll_one_line_down(event)
			self.layout.focus(self.prompt)

			if not self._scrolled_to_bottom:
				self.scroll_text.text = '(more)'
			else:
				self.scroll_text.text = ''

		self._app = Application(
			layout = self.layout,
			full_screen = True,
			key_bindings = key_bindings,
			style = style
		)

	@property
	def _scrolled_to_bottom(self):
		## True if the main output is scrolled to the bottom
		if self.scrolling_output.window.render_info == None:
			return True
		return (self.scrolling_output.window.vertical_scroll + self.scrolling_output.window.render_info.window_height) >= self.scrolling_output.window.render_info.content_height

	def build_completer(self):
		completions = {'?': {}}
		for module_name in self.modules:
			actions = {}
			for action in self.modules[module_name].available_admin_commands():
				actions[action] = None
			completions[module_name] = actions
			completions['?'][module_name] = actions

		self.prompt.completer = NestedCompleter.from_nested_dict(completions)

	def register_module(self, module):
		"""
		Modules are registered through the UI so we know about admin commands

		Args:
			module (instance): The instance of the module
		"""
		if module.module_name in self.modules:
			raise Exception('Duplicate module: {}'.format(module.module_name))
		self.modules[module.module_name] = module
		self.build_completer()

	def update_status_text(self, text=None):
		"""
		Update the status text on the bottom bar

		Args:
			text (string): String to show on the status bar. If None it will reset to default
		"""
		if text:
			self.status_text.text = text
			self.status_window.style = 'class:status-bar-important'
			self.scroll_window.style = 'class:status-bar-important'
		else:
			self.status_text.text = DEFAULT_STATUS
			self.status_window.style = 'class:status-bar'
			self.scroll_window.style = 'class:status-bar'
		self._app.invalidate()

	def run(self):
		self._app.run()

	def reset(self):
		self.modules = {}

	def terminate_mod_prompt(self, ident):
		"""
		Cancel the prompt identified by ident

		Args:
			ident (string): Indentifier for the prompt to be cancelled
		"""
		if self.prompt_ident == ident:
			self.module_prompt_callback = None
			self.mod_prompt()

	def mod_prompt(self, prompt=None, callback=None):
		"""
		Change the prompt to send input to <callback>.
		This is used in modules to receive user input

		Args:
			prompt (string): The prompt to display
			callback (func): Function to call when user input is received
		"""
		ident = uuid4().hex

		if self.module_prompt_callback and not callback:
			return

		if self.module_prompt_callback and callback:
			self.prompt_queue.put((prompt, callback, ident))
			return ident

		## Add prompts to a queue in case a module is already waiting on a prompt
		if not callback and not self.prompt_queue.empty():
			while not self.prompt_queue.empty():
				prompt, callback, ident = self.prompt_queue.get_nowait()
				if ident in self.prompt_ident_skip:
					self.prompt_ident_skip.remove(ident)
					prompt, callback, ident = (None, None, None)
				else:
					break

		self.prompt_ident = ident

		if prompt:
			prompt = prompt.strip()
			self.prompt_text.text = prompt
			self.prompt_window.width = len(prompt) + 1
		else:
			self.prompt_text.text = DEFAULT_PROMPT
			self.prompt_window.width = len(DEFAULT_PROMPT) + 1
		self.module_prompt_callback = callback

		## Must call invalidate on app to refresh UI
		self._app.invalidate()

		## Return the unique identifier
		return self.prompt_ident

	def input_recv(self, buff):
		"""
		The default function called upon user input to the prompt
		"""
		## If there is an active module wanting input, pass the data to
		## the appropriate function
		if self.module_prompt_callback:
			status = self.module_prompt_callback(self.prompt.text)
			if status:
				self.module_prompt_callback = None
				self.mod_prompt(None, None)
			return

		if self.prompt.text.strip().lower() == 'quit':
			self.buffer_queue.put('SHUTDOWN')
			self.buffer_thread.join()
			get_app().exit()
			return

		## Check for help command
		match = re.search(r'^\? ?([^ ]+)?( [^ ]+)?$', self.prompt.text)
		if match:
			module_name = match.group(1)
			command_name = match.group(2)
			if command_name:
				command_name = command_name.strip()

			self.show_help(module_name, command_name)
			return

		## Check for a valid command
		match = re.search(r'^([^ ]+) ([^ ]+) ?(.*)$', self.prompt.text)
		if match:
			module_name = match.group(1)
			trigger = match.group(2)
			params = match.group(3)

			self._execute_admin_command(module_name, trigger, params)

	def _execute_admin_command(self, module_name, trigger, params):
		## Execute an admin command for the appropriate module
		if not module_name in self.modules:
			pass
		elif trigger not in self.modules[module_name].available_admin_commands():
			pass
		else:
			command = self.modules[module_name].admin_command(trigger)
			command.execute(params.strip())

	def show_help(self, module=None, trigger=None):
		"""
		Output help text for <module>

		Args:
			module (string): Name of the module. If none display installed modules
			trigger (string): Module command. If None display valid commands for <module>
		"""
		if module and module in self.modules.keys():
			## Check for valid module and trigger
			if trigger and trigger in self.modules[module].available_admin_commands():
				help_str = 'Help for {module} {trigger}:\n'.format(
					module=module,
					trigger=trigger
				)
				command = self.modules[module].admin_command(trigger)
				help_str += '    ' + command.description + '\n'
				help_str += '    Usage: ' + command.usage

			else:
				## Module specified but no trigger
				help_str = ""
				if hasattr(self.modules[module], 'module_description'):
					help_str += self.modules[module].module_description.strip()
					help_str += '\n\n'
				help_str += f"Commands for {module} module:\n"
				count = 0
				this_line = "    "
				for trigger in self.modules[module].available_admin_commands():
					if count == 3:
						help_str += f"{this_line}\n"
						count = 0
						this_line = "    "

					this_line += trigger.ljust(20)
					count += 1

				help_str += "{}\n".format(this_line)

				help_str += f"Type '? {module} <command>' for more help."
			self.buffer_queue.put(("VOLTRON", '\n' + help_str + '\n'))
		else:
			## Show available modules
			help_str = "Available Modules:\n"
			for module_name in self.modules:
				if hasattr(self.modules[module_name], 'configurable') and not self.modules[module_name].configurable:
					continue
				help_str += "    {module_name}\n".format(
					module_name = module_name
				)
			help_str += "Type '? <module>' for more help."
			self.buffer_queue.put(('VOLTRON', '\n' + help_str + '\n'))

if __name__ == '__main__':
	ui = VoltronUI()
	ui.run()
