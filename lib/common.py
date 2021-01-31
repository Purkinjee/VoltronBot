import config
import sqlite3

from datetime import datetime, timedelta
from cryptography.fernet import Fernet
import time
import os

import requests
import json

from lib.TwitchAPIHelper import TwitchAPIHelper

def debug(message):
	"""
	Log a debug message if config.DEBUG is True

	Args:
		message (string): Debug message
	"""
	if config.DEBUG:
		print('DEBUG: ', message)

def get_module_directory(module = None):
	module_dir = config.APP_DIRECTORY + '\\' + config.USER_MODULES_DIRECTORY
	if module:
		module_dir += f'\\Modules\\{module}'

	if not os.path.isdir(module_dir):
		os.makedirs(module_dir)

	return module_dir

def get_module_data_directory(module = None):
	data_dir = config.APP_DIRECTORY + '\\ModuleData'

	if module:
		data_dir += f'\\{module}'

	if not os.path.isdir(data_dir):
		os.makedirs(data_dir)

	return data_dir

def get_db():
	"""
	Get a connection and cursor to the SQLite database and return in a tuple
	"""
	con = sqlite3.connect(config.DB)
	con.row_factory = _dict_factory
	cur = con.cursor()

	return (con, cur)

def get_broadcaster():
	"""
	Get a User object for the broadcaster, if one exists
	"""
	con, cur = get_db()

	sql = "SELECT id FROM oauth WHERE is_broadcaster = 1"
	cur.execute(sql)
	res = cur.fetchone()

	con.commit()
	con.close()

	if not res:
		debug("No broadcaster exists")
		return None

	return User(res['id'])

def get_default_user():
	"""
	Get a User object for the default account, if one exists
	"""
	con, cur = get_db()

	sql = "SELECT id FROM oauth WHERE is_default = 1"
	cur.execute(sql)
	res = cur.fetchone()

	con.commit()
	con.close()

	if not res:
		debug("No default exists")
		return get_broadcaster()

	return User(res['id'])

def get_user_by_twitch_id(twitch_id):
	con, cur = get_db()

	sql = "SELECT id FROM oauth WHERE twitch_user_id = ?"
	cur.execute(sql, (twitch_id, ))
	res = cur.fetchone()

	con.commit()
	con.close()

	if res:
		return User(res['id'])
	else:
		return None

def get_all_acccounts():
	"""
	Get a list of all users
	"""
	con, cur = get_db()
	users = []

	sql = "SELECT id FROM oauth ORDER BY is_broadcaster DESC, id"
	cur.execute(sql)
	res = cur.fetchall()

	for r in res:
		users.append(User(r['id']))

	con.commit()
	con.close()

	return users

class OauthTokens:
	"""
	Class to store, manage, and refresh OAuth tokens
	"""
	def __init__(self, oauth_token, refresh_token, expire_time, user_id = None):
		## PRODUCTION ##
		########
		## SET CLIENT_ID AND CLIENT SECRET HERE FOR PRODUCTION
		########
		self.__client_id = ''
		self.__client_secret = ''

		if hasattr(config, 'CLIENT_ID'):
			self.__client_id = config.CLIENT_ID
		if hasattr(config, 'CLIENT_SECRET'):
			self.__client_secret = config.CLIENT_SECRET
		self._oauth_token = oauth_token
		self._refresh_token = refresh_token
		if type(expire_time) == type(''):
			self._expire_time = datetime.fromisoformat(expire_time)
		else:
			self._expire_time = expire_time
		self._last_validation_time = 0
		self._user_id = user_id

	def token(self, fernet_key):
		if (time.time() - self._last_validation_time) > 600: # 10 minutes
			self.validate_auth(fernet_key)

		tte = (self._expire_time - datetime.now()).total_seconds()
		if tte < 1800: # 30 minutes
			self.refresh_auth(fernet_key)

		cipher = Fernet(fernet_key)
		return cipher.decrypt(self._oauth_token).decode()

	def validate_auth(self, fernet_key):
		cipher = Fernet(fernet_key)
		token = cipher.decrypt(self._oauth_token).decode()
		headers = {
			"Authorization" : "OAuth {access_token}".format(access_token=token)
		}
		try:
			req = requests.get(
				'https://id.twitch.tv/oauth2/validate',
				headers = headers
			)
		except requests.exceptions.ConnectionError:
			return False
		resp = json.loads(req.text)
		if (
			resp
			and 'client_id' in resp
			and resp['client_id'] == self.__client_id
			and 'expires_in' in resp
			and resp['expires_in'] > 1800
		):
			self._last_validation_time = time.time()
			return True
		else:
			return self.refresh_auth(fernet_key)

	def refresh_auth(self, fernet_key):
		cipher = Fernet(fernet_key)
		refresh_token = cipher.decrypt(self._refresh_token).decode()
		body = {
			'client_id': self.__client_id,
			'client_secret': self.__client_secret,
			'grant_type': 'refresh_token',
			'refresh_token': refresh_token,
			'scope': config.SCOPES
		}
		try:
			req = requests.post(
				'https://id.twitch.tv/oauth2/token',
				data=body
			)
		except requests.exceptions.ConnectionError:
			return False

		token_data = json.loads(req.text)

		if 'access_token' in token_data and 'refresh_token' in token_data:
			#self._oauth_token = token_data['access_token']
			#self._refresh_token = token_data['refresh_token']
			self._expire_time = datetime.now() + timedelta(seconds=token_data['expires_in'])

			encrypt_token = cipher.encrypt(token_data['access_token'].encode())
			encrypt_refresh = cipher.encrypt(token_data['refresh_token'].encode())
			self._oauth_token = encrypt_token
			self._refresh_token = encrypt_refresh

			if self._user_id:
				con, cur = get_db()
				sql = "UPDATE oauth SET oauth_token = ?, refresh_token = ?, token_expire_time = ? WHERE id = ?"
				cur.execute(sql,(
					encrypt_token,
					encrypt_refresh,
					self._expire_time,
					self._user_id
				))

				con.commit()
				con.close()
			self._last_validation_time = time.time()
			return True

		return False

class User:
	"""
	Class for Users

	Args:
		user_id (int): id in the oauth table in the database
	"""
	def __init__(self, user_id):
		self.id = user_id
		self.oauth_tokens = None
		self.refresh()
		self.twitch_api = TwitchAPIHelper(self.oauth_tokens)

	def update(self):
		user_info = self.twitch_api.get_this_user()
		data = user_info.get('data', [])
		if not data:
			debug('No user data found')
			return
		this_user = data[0]

		con, cur = get_db()

		sql = "UPDATE oauth SET user_name = ?, display_name = ? WHERE id = ?"
		cur.execute(sql, (this_user['login'], this_user['display_name'], self.id))

		con.commit()
		con.close()
		self.refresh()

	def refresh(self):
		con, cur = get_db()

		sql = "SELECT * FROM oauth WHERE id = ?"
		cur.execute(sql, (self.id,))
		res = cur.fetchone()

		con.commit()
		con.close()

		## Raise an exception if the user cannot be found in the DB
		if not res:
			raise Exception("User does not exist")

		## For now we will just set instance variables for each field in
		## the database
		for key in res:
			if key in ['is_broadcaster', 'is_default']:
				res[key] = True if res[key] else False

			setattr(self, key, res[key])

		## Create an OauthTokens object to manage the tokens for this user
		self.oauth_tokens = OauthTokens(
			res['oauth_token'],
			res['refresh_token'],
			res['token_expire_time'],
			user_id = self.id
		)

	def make_broadcaster(self):
		con, cur = get_db()

		cur.execute('UPDATE oauth SET is_broadcaster = 0')
		cur.execute('UPDATE oauth SET is_broadcaster = 1 WHERE id = ?', (self.id, ))

		con.commit()
		con.close()

	def make_default(self):
		con, cur = get_db()

		cur.execute('UPDATE oauth SET is_default = 0')
		cur.execute('UPDATE oauth SET is_default = 1 WHERE id = ?', (self.id, ))

		con.commit()
		con.close()

	def delete(self):
		con, cur = get_db()

		cur.execute('DELETE FROM oauth WHERE id = ?', (self.id, ))

		con.commit()
		con.close()

## Dict factory used for creating dictionaries from SQLite query results
def _dict_factory(cursor, row):
	d = {}
	for idx, col in enumerate(cursor.description):
		d[col[0]] = row[idx]
	return d
