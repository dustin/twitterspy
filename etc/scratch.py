#!/usr/bin/env python

import sys
sys.path.extend(['lib', '../lib'])

from twisted.internet import defer, reactor

from twitterspy import db

@defer.deferredGenerator
def f():
    d = db.User.by_jid('dustin@sallings.org')
    wfd = defer.waitForDeferred(d)
    yield wfd
    u = wfd.getResult()
    print "%s tracks %s" % (u.jid, str(u.tracks))

    reactor.stop()

reactor.callWhenRunning(f)
reactor.run()
