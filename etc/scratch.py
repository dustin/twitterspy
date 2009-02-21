#!/usr/bin/env python

import sys
sys.path.extend(['lib', '../lib'])

from twisted.internet import defer, reactor

from twitterspy import db

@defer.deferredGenerator
def f():
    d = db.get_active_users()
    wfd = defer.waitForDeferred(d)
    yield wfd
    u = wfd.getResult()
    print u

    reactor.stop()

reactor.callWhenRunning(f)
reactor.run()
