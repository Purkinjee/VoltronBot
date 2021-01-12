import os
## Directory for all Voltron modules
APP_DIRECTORY = os.environ['APPDATA'] + '\\VoltronBot'
DB = APP_DIRECTORY + '\\data.db'

## Set to true for production mode
PRODUCTION = False

## If DEBUG=False no output will be displayed for debug messages
DEBUG = False

## Which messages to display in UI in ascending severity:
## INFO WARN ERR CRIT
LOG_LEVEL = 'INFO'

## To log data we aren't using
IRC_LOG_FILE = "irc.log"
LOG_IRC_DATA = True

DEFAULT_SOCKET_TIMEOUT = 60
OAUTH_HTTPD_PORT = 80

## Client ID for the twitch app.
## Register a developer app on Twitch to get one
## https://dev.twitch.tv/console/apps
CLIENT_ID = "put client id here"
CLIENT_SECRET = "put client secret here"
SCOPES = "user:read:email chat:edit chat:read"
FERNET_KEY = b'put fernet key here for enctrypting OAuth tokens'
