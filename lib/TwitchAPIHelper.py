import config
import requests
import json
from datetime import datetime, timezone, timedelta

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

	def set_stream_title(self, broadcaster_id, title):
		"""
		Sets the stream title for the bearer of self.oauth_tokens
		"""
		if not title:
			return False
		try:
			req = requests.patch(
				'https://api.twitch.tv/helix/channels',
				headers = {
					'client-id': self.__client_id,
					'Authorization': 'Bearer {token}'.format(token=self.oauth_tokens.token(self.__fernet_key))
				},
				params = {
					'broadcaster_id': broadcaster_id,
					'title': title
				}
			)
		except requests.exceptions.ConnectionError:
			return False

		if req.status_code == 204:
			return self.get_channel(broadcaster_id)
		return False

	def set_stream_game(self, broadcaster_id, game_name):
		if not game_name:
			return None
		game_id = self.get_game_id(game_name)
		if not game_id:
			return game_id

		try:
			req = requests.patch(
				'https://api.twitch.tv/helix/channels',
				headers = {
					'client-id': self.__client_id,
					'Authorization': 'Bearer {token}'.format(token=self.oauth_tokens.token(self.__fernet_key))
				},
				params = {
					'broadcaster_id': broadcaster_id,
					'game_id': game_id
				}
			)
		except requests.exceptions.ConnectionError:
			return False

		return self.get_channel(broadcaster_id)


	def get_game_id(self, game_name):
		"""
		The the game ID for use on twitch from game_name
		"""
		try:
			req = requests.get(
				'https://api.twitch.tv/helix/search/categories',
				headers = {
					'client-id': self.__client_id,
					'Authorization': 'Bearer {token}'.format(token=self.oauth_tokens.token(self.__fernet_key))
				},
				params = {
					'query': game_name,
					'first': 1
				}
			)
		except requests.exceptions.ConnectionError:
			return False

		resp = json.loads(req.text)
		if 'data' in resp and len(resp['data']) > 0:
			return int(resp['data'][0]['id'])
		else:
			return None

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

	def get_follow_time(self, broadcaster_id, user_id):
		try:
			req = requests.get(
				'https://api.twitch.tv/helix/channels/followers',
				headers = {
					'client-id': self.__client_id,
					'Authorization': 'Bearer {}'.format(self.oauth_tokens.token(self.__fernet_key))
				},
				params = {
					'user_id' : user_id,
					'broadcaster_id': broadcaster_id
				}
			)
		except requests.exceptions.ConnectionError:
			return False

		resp = json.loads(req.text)
		data = resp.get('data', None)

		if not data or len(data) < 1:
			return None

		data = data[0]
		followed_at = datetime.strptime(data['followed_at'], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone(timedelta(0)))
		now = datetime.utcnow().replace(tzinfo=timezone(timedelta(0)))
		secs = (now - followed_at).total_seconds()

		return secs

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
