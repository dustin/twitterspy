CREATE TABLE tracks (
    id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    query VARCHAR(50) NOT NULL,
    max_seen INTEGER);

CREATE TABLE "user_tracks" (
       id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
       user_id INTEGER NOT NULL,
       track_id INTEGER NOT NULL,
       created_at DATETIME);

CREATE TABLE "users" (
       id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
       jid VARCHAR(128) NOT NULL,
       service_jid VARCHAR(128) NULL,
       username VARCHAR(50),
       password VARCHAR(50),
       active BOOLEAN NOT NULL DEFAULT 't',
       status VARCHAR(50),
       min_id INTEGER NOT NULL DEFAULT 0,
       language VARCHAR(2),
       auto_post BOOLEAN NOT NULL DEFAULT 'f',
       friend_timeline_id integer,
       direct_message_id integer,
       created_at timestamp);

CREATE UNIQUE INDEX unique_index_user_tracks_id ON user_tracks (id);
CREATE UNIQUE INDEX unique_index_user_tracks_idx_ut_ut ON user_tracks (user_id, track_id);
CREATE UNIQUE INDEX unique_index_users_id ON users (id);
CREATE UNIQUE INDEX unique_index_users_jid ON users (jid);
