import config
import requests
import json

class TwitchAPIHelper:
	"""
	Helper for sending requests and parsing responses from the Twitch API

	Args:
		oauth_tokens (OauthTokens()): OauthTokens object for making requests
	"""
	def __init__(self, oauth_tokens):
		self.oauth_tokens = oauth_tokens
		## PRODUCTION ##
		######
		## SET CLIENT_ID AND FERNET_KEY HERE FOR PRODUCTION
		######
		self.__client_id = ''
		self.__fernet_key = ''

		if hasattr(config, 'CLIENT_ID'):
			self.__client_id = config.CLIENT_ID

		if hasattr(config, 'FERNET_KEY'):
			self.__fernet_key = config.FERNET_KEY

	def get_this_user(self):
		"""
		Get Twitch user information for the holder of self.oauth_tokens
		"""
		try:
			req = requests.get(
				'https://api.twitch.tv/helix/users',
				headers = {
					'client-id': self.__client_id,
					'Authorization': 'Bearer {token}'.format(token=self.oauth_tokens.token(self.__fernet_key))
				},
			)
		except requests.exceptions.ConnectionError:
			return False
		resp = json.loads(req.text)
		return resp

	def get_user(self, login):
		try:
			req = requests.get(
				'https://api.twitch.tv/helix/users',
				headers = {
					'client-id': self.__client_id,
					'Authorization': 'Bearer {token}'.format(token=self.oauth_tokens.token(self.__fernet_key))
				},
				params = {'login': login}
			)
		except requests.exceptions.ConnectionError:
			return False

		resp = json.loads(req.text)

		data = resp.get('data', None)
		if not data or len(data) < 1:
			return None

		return data[0]

	def get_rewards(self, broadcaster_id):
		try:
			req = requests.get(
				'https://api.twitch.tv/helix/channel_points/custom_rewards',
				headers = {
					'client-id': self.__client_id,
					'Authorization': 'Bearer {}'.format(self.oauth_tokens.token(self.__fernet_key))
				},
				params = { 'broadcaster_id': broadcaster_id }
			)
		except requests.exceptions.ConnectionError:
			return False

		resp = json.loads(req.text)
		data = resp.get('data', None)

		return data

	def get_stream(self, broadcaster_id):
		try:
			req = requests.get(
				'https://api.twitch.tv/helix/streams',
				headers = {
					'client-id': self.__client_id,
					'Authorization': 'Bearer {}'.format(self.oauth_tokens.token(self.__fernet_key))
				},
				params = { 'user_id': broadcaster_id }
			)
		except requests.exceptions.ConnectionError:
			return False
		resp = json.loads(req.text)
		data = resp.get('data', None)
		if not data or len(data) < 1:
			return None

		return data[0]

	def get_channel(self, broadcaster_id):
		try:
			req = requests.get(
				'https://api.twitch.tv/helix/channels',
				headers = {
					'client-id': self.__client_id,
					'Authorization': 'Bearer {token}'.format(token=self.oauth_tokens.token(self.__fernet_key))
				},
				params = {'broadcaster_id': broadcaster_id}
			)
		except requests.exceptions.ConnectionError:
			return False

		resp = json.loads(req.text)
		data = resp.get('data', None)
		if not data or len(data) < 1:
			return None

		return data[0]
