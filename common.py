import config
import sqlite3

def debug(message):
	"""
	Log a debug message if config.DEBUG is True

	Args:
		message (string): Debug message
	"""
	if config.DEBUG:
		print('DEBUG: ', message)

def get_db():
	"""
	Get a connection and cursor to the SQLite database and return in a tuple
	"""
	con = sqlite3.connect('data.db')
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

class OauthTokens:
	"""
	Class to store, manage, and refresh OAuth tokens
	"""
	def __init__(self, oauth_token, refresh_token, expire_time):
		self._oauth_token = oauth_token
		self._refresh_token = refresh_token
		self._expire_time = expire_time

	@property
	def token(self):
		return self._oauth_token

class User:
	"""
	Class for Users

	Args:
		user_id (int): id in the oauth table in the database
	"""
	def __init__(self, user_id):
		con, cur = get_db()

		sql = "SELECT * FROM oauth WHERE id = ?"
		cur.execute(sql, (user_id,))
		res = cur.fetchone()

		con.commit()
		con.close()

		## Raise an exception if the user cannot be found in the DB
		if not res:
			raise Exception("User does not exist")

		## For now we will just set instance variables for each field in
		## the database
		for key in res:
			setattr(self, key, res[key])

		## Create an OauthTokens object to manage the tokens for this user
		self.oauth_tokens = OauthTokens(
			res['oauth_token'],
			res['refresh_token'],
			res['token_expire_time']
		)

## Dict factory used for creating dictionaries from SQLite query results
def _dict_factory(cursor, row):
	d = {}
	for idx, col in enumerate(cursor.description):
		d[col[0]] = row[idx]
	return d
