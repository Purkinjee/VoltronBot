import http.server
from random import randint
import hashlib
import webbrowser
from urllib.parse import parse_qs
import requests
import json
from datetime import datetime, timedelta
from cryptography.fernet import Fernet

from lib.common import debug, OauthTokens, get_db, User, get_user_by_twitch_id
from lib.TwitchAPIHelper import TwitchAPIHelper
import config

class OauthRequestHandler(http.server.BaseHTTPRequestHandler):
	## This function will be called whenever the webserver
	## receives a GET request
	def do_GET(self):
		## Make sure a query string exists
		try:
			path, qs = self.path.split('?', 1)
		except ValueError:
			#debug('Error pasring request URL')
			return
		get = parse_qs(qs)

		## PRODUCTION ##
		########
		## SET CLIENT_ID AND CLIENT SECRET HERE FOR PRODUCTION
		########
		client_id = ''
		client_secret = ''
		if hasattr(config, 'CLIENT_ID'):
			client_id = config.CLIENT_ID
		if hasattr(config, 'CLIENT_SECRET'):
			client_secret = config.CLIENT_SECRET

		## Check for an abort request
		action = get.get('action', None)
		if action and action[0] == 'abort':
			self.send_response(200)
			self.send_header("Content-type", "text/html")
			self.end_headers()
			self.wfile.write('Authorization aborted'.encode('utf8'))
			return

		## Twitch sends us a unique code that has to be sent back
		## in the next request and has to match
		code = get.get('code', False)
		if not code:
			debug("Code does not exist in request")
			return
		code = code[0]

		## This is the unique state that we sent to Twitch when we requested
		## the Oauth authentication. If it doesn't match, something shady might
		## be going on
		state = get.get('state', False)
		if not state:
			debug("State does not exist in request")
			return

		## Don't do anything if the state doesn't match
		## This could mean an attempt to fake a user login
		if state[0] != self.server.state:
			debug("State does not match!")
			return

		## Everything looks good, so let's prepare the next request
		## and validate everything
		body = {
			'client_id': client_id,
			'client_secret': client_secret,
			'code': code,
			'grant_type': 'authorization_code',
			'redirect_uri' : 'http://localhost/'
		}
		req = requests.post(
			'https://id.twitch.tv/oauth2/token',
			data=body
		)
		data = json.loads(req.text)

		## If we get the expected response back, set the appropriate variables
		## in self.server and send a 200 (success) response to the browser
		if 'access_token' in data and 'refresh_token' in data:
			self.server.auth_success = True
			self.server.access_token = data['access_token']
			self.server.refresh_token = data['refresh_token']
			self.server.expires_in = data['expires_in']

		self.send_response(200)
		self.send_header("Content-type", "text/html")
		self.end_headers()
		self.wfile.write('Authorization success! You can close this window.'.encode('utf8'))

	## Overriade log_message so we don't get a bunch of garbage output
	## in the console
	def log_message(self, format, *args):
		return

## Class for the HTTP server used to capture the authentication information
class OauthResponseServer(http.server.HTTPServer):
	def __init__(self, state, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.state = state

		self.auth_success = False
		self.access_token = False
		self.refresh_token = False
		self.expires_in = None

def save_oauth(oauth_token, refresh_token, expires_in, is_broadcaster):
	"""
	Fetch all of the user information from the Twitch API and save it to the database

	Args:
		oauth_token (string): OAuth token received from Twitch
		refresh_token (string): Refresh token received from Twitch
		expires_in (int): Number of seconds until oauth_token expires
		is_broadcaster (bool): True if this is the broadcaster account
	"""
	## Calcuate the exact expire time based off how many seconds the token
	## is valid. Fetch all of the user information from the Twitch API
	## and save it to our database
	expire_time = datetime.now() + timedelta(seconds=expires_in)
	cipher = Fernet(config.FERNET_KEY)
	oauth_token = cipher.encrypt(oauth_token.encode())
	refresh_token = cipher.encrypt(refresh_token.encode())

	token = OauthTokens(oauth_token, refresh_token, expire_time)
	api = TwitchAPIHelper(token)
	user_info = api.get_this_user()

	data = user_info.get('data', [])
	if not data:
		debug('No user data found')
		return
	this_user = data[0]

	con, cur = get_db()

	## If this is the broadcaster we need to check if a broadcaster already
	## exists in the database
	if is_broadcaster:
		sql = "SELECT id, user_name FROM oauth WHERE is_broadcaster = 1"
		cur.execute(sql)
		res = cur.fetchone()
		if res:
			debug("Broadcaster Already Exists!")
			## Broadcaster already exists and we should do somthing about it
			sql = "UPDATE oauth SET is_broadcaster = 0 WHERE is_broadcaster = 1"
			#sql = "DELETE FROM oauth WHERE is_broadcaster = 1"
			cur.execute(sql)
			con.commit()

	## SQLite doesn't support booleans so convert to an integer
	is_broadcaster_int = int(is_broadcaster == True)

	## If an account already exists for this twitch user, update the
	## existing account
	existing = get_user_by_twitch_id(this_user['id'])
	new_user = None
	sql = 'SELECT id FROM oauth WHERE is_default = 1'
	cur.execute(sql)
	default = cur.fetchone()
	is_default = 0 if default else 1
	if existing:
		sql = "UPDATE oauth SET \
		user_name = ?, \
		login_time = datetime('now'), \
		display_name = ?, \
		oauth_token = ?, \
		refresh_token = ?, \
		token_expire_time = ?, \
		is_broadcaster = ? \
		is_default = ? \
		WHERE id = ? \
		"
		cur.execute(sql, (
			this_user['login'],
			this_user['display_name'],
			oauth_token,
			refresh_token,
			expire_time,
			is_broadcaster_int,
			is_default,
			existing.id
		))
		con.commit()
		new_user = existing
		new_user.refresh()
	else:
		sql = "INSERT INTO oauth \
			(user_name, login_time, display_name, twitch_user_id, oauth_token, refresh_token, token_expire_time, is_broadcaster, is_default) \
			VALUES (?, datetime('now'), ?, ?, ?, ?, ?, ?, ?)"

		cur.execute(sql, (
			this_user['login'],
			this_user['display_name'],
			this_user['id'],
			oauth_token,
			refresh_token,
			expire_time,
			is_broadcaster_int,
			is_default
			)
		)
		con.commit()
		new_user = User(cur.lastrowid)
	con.close()

	return new_user

def twitch_login():
	## PRODUCTION ##
	########
	## SET CLIENT ID HERE FOR PRODUCTION
	########
	client_id = ''
	if hasattr(config, 'CLIENT_ID'):
		client_id = client_id
	## Create a random state string and salt it with mayo (for now)
	state_id = randint(0,1000000)
	hash_str = "%s%s" % ('mayo', state_id)
	md5 = hashlib.md5(hash_str.encode()).hexdigest()
	url = (
		'https://id.twitch.tv/oauth2/authorize?'
		'response_type=code'
		'&client_id={client_id}'
		'&redirect_uri=http://localhost/'
		'&response_type=token'
		'&scope={scope}'
		'&state={state}'
		'&force_verify=true'
	).format(
		client_id = client_id,
		state = md5,
		scope = config.SCOPES.replace(' ', '%20')
	)

	## Open the webbrowser and show the url we just created
	webbrowser.open(url, autoraise=True)

	## Start the HTTP server and wait for a response
	httpd = OauthResponseServer(md5, ('', config.OAUTH_HTTPD_PORT), OauthRequestHandler)
	httpd.handle_request()

	if not httpd.auth_success:
		return False

	## Return the tokens
	return (httpd.access_token, httpd.refresh_token, httpd.expires_in)
