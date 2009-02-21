#!/usr/bin/env python

import sys
sys.path.extend(["lib", "../lib"])

from sqlite3 import dbapi2 as sqlite

from twisted.internet import reactor, defer

from twitterspy import db

GET_USERS="""
select jid, username, password, active, status, min_id, language,
       auto_post, friend_timeline_id, direct_message_id, created_at, id
    from users
"""

GET_TRACKS="""
select query
    from tracks join user_tracks on (tracks.id = user_tracks.track_id)
    where user_tracks.user_id = ?
"""

DB=sqlite.connect(sys.argv[1])

CUR=DB.cursor()

def parse_timestamp(ts):
    return None

def create(e, r):
    print "Creating record for", r[0]
    user = db.User()
    user.jid = r[0]
    user.username = r[1]
    user.password = r[2]
    user.active = bool(r[3])
    user.status = r[4]
    user.min_id = r[5]
    user.language = r[6]
    user.auto_post = bool(r[7])
    user.friend_timeline_id = r[8]
    user.direct_message_id = r[9]
    user.created_at = parse_timestamp(r[10])

    for tr in CUR.execute(GET_TRACKS, [r[11]]).fetchall():
        user.track(tr[0])

    return user.save()

@defer.deferredGenerator
def load_records():
    couch = db.get_couch()

    for r in CUR.execute(GET_USERS).fetchall():
        d = couch.openDoc(db.DB_NAME, str(r[0]))
        d.addErrback(create, r)
        wfd = defer.waitForDeferred(d)
        yield wfd

    reactor.stop()

reactor.callWhenRunning(load_records)
reactor.run()
