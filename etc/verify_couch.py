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

DB=sqlite.connect(sys.argv[1])

CUR=DB.cursor()

def parse_timestamp(ts):
    return None

@defer.deferredGenerator
def verify_users():
    couch = db.get_couch()
    for r in CUR.execute(GET_USERS).fetchall():
        d = couch.openDoc(db.DB_NAME, str(r[0]))
        d.addErrback(lambda x: sys.stdout.write("Can't find %s\n" % r[0]))
        wfd = defer.waitForDeferred(d)
        yield wfd

    reactor.stop()

reactor.callWhenRunning(verify_users)
reactor.run()
