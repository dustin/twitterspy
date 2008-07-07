create unique index idx_user_by_jid on users(jid);
create unique index idx_user_by_id on users(id);

create unique index idx_watch_by_urluser on watches(url, user_id);
create unique index idx_watch_by_id on watches(id);
create index idx_watch_by_user on watches(user_id);

create unique index idx_pattern_by_id on patterns(id);
create index idx_pattern_by_watch on patterns(watch_id);
