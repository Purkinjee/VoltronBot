CREATE TABLE oauth (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	user_name CHAR(100) NOT NULL,
	login_time DATETIME NOT NULL,
	display_name CHAR(100) NOT NULL,
	twitch_user_id INTEGER NOT NULL,
	oauth_token CHAR(255) NOT NULL,
	refresh_token CHAR(255) DEFAULT NULL,
	token_expire_time DATETIME NOT NULL,
	is_broadcaster INTEGER NOT NULL DEFAULT 0,
	is_default INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE module_data (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	module_name CHAR(255) NOT NULL UNIQUE,
	data TEXT NOT NULL
);
