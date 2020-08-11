import threading
from queue import Queue
import requests
import sys

from base.module import ModuleBase, ModuleAdminCommand
from lib.twitch_oauth import twitch_login, save_oauth, User
from lib.common import get_all_acccounts, get_broadcaster, get_user_by_twitch_id
import config

class GetTwitchLogin(threading.Thread):
	"""
	Thread for waiting for login information
	"""
	def __init__(self, module, input_queue):
		threading.Thread.__init__(self)
		self.module = module

	def run(self):
		login_info = twitch_login()
		self.module.login_thread_done(login_info)
		sys.exit()

class Account(ModuleBase):
	"""
	Core module for managing accounts
	"""
	module_name = 'account'
	def setup(self):
		self.login_thread = None
		self.login_thread_queue = Queue()
		self.prompt_ident = None

		## Define commands
		self.register_admin_command(ModuleAdminCommand(
			'add',
			self.add_account,
			usage = 'account add',
			description = 'Add a new Twtich account.'
		))

		self.register_admin_command(ModuleAdminCommand(
			'list',
			self.list_accounts,
			usage = 'account list',
			description = 'List all accounts.'
		))

		self.register_admin_command(ModuleAdminCommand(
			'refresh',
			self.refresh_accounts,
			usage = 'account refresh',
			description = 'Update all accounts using Twitch API'
		))

		self.register_admin_command(ModuleAdminCommand(
			'default',
			self.set_default,
			usage = 'account default',
			description = 'Set the default account to send chat messages'
		))

		self.register_admin_command(ModuleAdminCommand(
			'broadcaster',
			self.set_broadcaster,
			usage = 'account broadcaster',
			description = 'Set the broadcaster account'
		))

		self.register_admin_command(ModuleAdminCommand(
			'delete',
			self.remove_account,
			usage = 'account delete',
			description = 'Delete an account.'
		))

	def add_account(self):
		self.buffer_print('VOLTRON', 'Authorizing new account...')
		self.buffer_print('VOLTRON', 'Type C to cancel')
		self.update_status_text('Awaiting auth...')
		self.prompt_ident = self.get_prompt('c to cancel>> ', self.input_recv)
		self.login_thread = GetTwitchLogin(self, self.login_thread_queue)
		self.login_thread.start()

	def refresh_accounts(self):
		for account in self.voltron.users:
			account.update()
			self.buffer_print('VOLTRON', '{} updated'.format(account.display_name))
		self.buffer_print('VOLTRON', 'Update Complete!')

	def set_default(self):
		## This will list all accounts, allow the user to select
		## one to make default, or cancel
		account_list = self.list_accounts()

		def select_account(prompt):
			if prompt.lower().strip() == 'c':
				self.update_status_text()
				return True
			try:
				selection = int(prompt)
			except:
				return False

			if selection < 0 or selection > len(account_list):
				self.buffer_print('VOLTRON', 'Invalid selection')
				return False

			selected_user = User(account_list[selection-1])

			def confirm(prompt):
				prompt = prompt.lower().strip()
				if prompt == 'n':
					self.update_status_text()
					return True
				if prompt != 'y':
					return False

				selected_user.make_default()
				self.buffer_print('VOLTRON', '{} is now the default account, restarting.'.format(selected_user.display_name))
				self.update_status_text()
				self.voltron.reset()
				self.voltron.start()
				return True

			self.update_status_text('Set default account to {}?'.format(selected_user.display_name))
			self.terminate_prompt(self.prompt_ident)
			self.prompt_ident = self.get_prompt('[Y]es/[N]o> ', confirm)

		self.update_status_text('Select account to make default, c to cancel')
		self.prompt_ident = self.get_prompt('Account Number> ', select_account)

	def set_broadcaster(self):
		## This will list all accounts, allow the user to select
		## one to make broadcaster, or cancel
		account_list = self.list_accounts()

		def select_account(prompt):
			if prompt.lower().strip() == 'c':
				self.update_status_text()
				return True
			try:
				selection = int(prompt)
			except:
				return False

			if selection < 0 or selection > len(account_list):
				self.buffer_print('VOLTRON', 'Invalid selection')
				return False

			selected_user = User(account_list[selection-1])

			def confirm(prompt):
				prompt = prompt.lower().strip()
				if prompt == 'n':
					self.update_status_text()
					return True
				if prompt != 'y':
					return False

				selected_user.make_broadcaster()
				self.buffer_print('VOLTRON', '{} is now the broadcaster, restarting.'.format(selected_user.display_name))
				self.update_status_text()
				self.voltron.reset()
				self.voltron.start()
				return True

			self.update_status_text('Set broadcaster account to {}?'.format(selected_user.display_name))
			self.terminate_prompt(self.prompt_ident)
			self.prompt_ident = self.get_prompt('[Y]es/[N]o> ', confirm)

		self.update_status_text('Select account to make broadcaster, c to cancel')
		self.prompt_ident = self.get_prompt('Account Number> ', select_account)

	def remove_account(self):
		account_list = self.list_accounts()

		def select_account(prompt):
			if prompt.lower().strip() == 'c':
				self.update_status_text()
				return True
			try:
				selection = int(prompt)
			except:
				return False

			if selection < 0 or selection > len(account_list):
				self.buffer_print('VOLTRON', 'Invalid selection')
				return False

			selected_user = User(account_list[selection-1])

			def confirm(prompt):
				prompt = prompt.lower().strip()
				if prompt == 'n':
					self.update_status_text()
					return True
				if prompt != 'y':
					return False

				selected_user.delete()
				self.buffer_print('VOLTRON', '{} deleted, restarting.'.format(selected_user.display_name))
				self.update_status_text()
				self.voltron.reset()
				self.voltron.start()
				return True

			self.update_status_text('Delete account {}?'.format(selected_user.display_name))
			self.terminate_prompt(self.prompt_ident)
			self.prompt_ident = self.get_prompt('[Y]es/[N]o> ', confirm)

		self.update_status_text('Select account to delete, c to cancel')
		self.prompt_ident = self.get_prompt('Account Number> ', select_account)

	def list_accounts(self):
		users = get_all_acccounts()
		count = 1
		self.buffer_print('VOLTRON', '')
		account_list = []
		for user in users:
			output_str = '{num}. {display} default={default} broadcaster={broadcaster}'.format(
				num = count,
				display = user.display_name,
				channel = user.user_name,
				default = user.is_default,
				broadcaster = user.is_broadcaster
			)
			account_list.append(user.id)
			self.buffer_print('VOLTRON', output_str)
			count += 1
		self.buffer_print('VOLTRON', '')
		return account_list

	def login_thread_done(self, login_info):
		## Called from the login thread upon completion
		## This is where we save new account information
		self.update_status_text()
		if self.prompt_ident:
			self.terminate_prompt(self.prompt_ident)
		if not login_info:
			self.buffer_print('VOLTRON', 'Authorization failed')
			return

		def save(prompt):
			action = prompt.lower().strip()
			if action == 'c':
				self.buffer_print('VOLTRON', 'No account added')
				return True
			elif action == 'y':
				is_broadcaster = True
			elif action == 'n':
				is_broadcaster = False
			else:
				return False

			def confirm(prompt):
				action = prompt.lower().strip()
				if action == 'n':
					return True
				elif action != 'y':
					return False

				account = save_oauth(
					login_info[0], # oauth token
					login_info[1], # refresh_token
					login_info[2], # expires in
					is_broadcaster # is broadcaster
				)

				self.buffer_print('VOLTRON', 'Authorization successful for {user} (broadcaster={broadcaster})'.format(
					user=account.display_name,
					broadcaster = is_broadcaster
				))
				self.update_status_text()
				self.get_prompt()
				self.voltron.reset()
				self.voltron.start()
				return True

			broadcaster = get_broadcaster()
			if broadcaster and is_broadcaster:
				self.update_status_text('Replace current broadcaster account ({})'.format(
					broadcaster.display_name
				))
				self.terminate_prompt(self.prompt_ident)
				self.prompt_ident = self.get_prompt('[Y]es/[N]o> ', confirm)
			else:
				return confirm('y')

		self.update_status_text('Is this the broadcaster account?')
		self.prompt_ident = self.get_prompt('[Y]es/[N]o/[C]ancel> ', save)

	def input_recv(self, input):
		## use this function to see if the user wants to cancel authentation
		## If so, terminate the thread and reset
		if input.lower().strip() == 'c':
			self.buffer_print('VOLTRON', 'Cancelling...')
			if self.login_thread:
				requests.get(
					'http://localhost:{}'.format(config.OAUTH_HTTPD_PORT),
					params = { 'action': 'abort' }
				)
			self.prompt_ident = None
			return True
		return False
