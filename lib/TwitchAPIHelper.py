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

	def get_this_user(self):
		"""
		Get Twitch user information for the holder of self.oauth_tokens
		"""
		req = requests.get(
			'https://api.twitch.tv/helix/users',
			headers = {
				'client-id': config.CLIENT_ID,
				'Authorization': 'Bearer {token}'.format(token=self.oauth_tokens.token)
			},
		)
		resp = json.loads(req.text)
		return resp

	def get_user(self, login):
		req = requests.get(
			'https://api.twitch.tv/helix/users',
			headers = {
				'client-id': config.CLIENT_ID,
				'Authorization': 'Bearer {token}'.format(token=self.oauth_tokens.token)
			},
			params = {'login': login}
		)

		resp = json.loads(req.text)

		data = resp.get('data', None)
		if not data or len(data) < 1:
			return None

		return data[0]

	def get_channel(self, broadcaster_id):
		req = requests.get(
			'https://api.twitch.tv/helix/channels',
			headers = {
				'client-id': config.CLIENT_ID,
				'Authorization': 'Bearer {token}'.format(token=self.oauth_tokens.token)
			},
			params = {'broadcaster_id': broadcaster_id}
		)

		resp = json.loads(req.text)
		data = resp.get('data', None)
		if not data or len(data) < 1:
			return None
			
		return data[0]
