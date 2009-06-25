import sys
import xml

from twisted.trial import unittest
from twisted.internet import defer, reactor

sys.path.extend(['lib', '../lib',
                 'lib/twitterspy', '../lib/twitterspy',
                 'lib/wokkel/', '../lib/wokkel/',
                 'lib/twisted-longurl/lib', '../lib/twisted-longurl/lib/',
                 'lib/twitty-twister/lib', '../lib/twitty-twister/lib'])

import cache
import scheduling

class FakeTwitterAPI(object):

    def __init__(self, res):
        self.res = res

    def search(self, query, cb, params):
        def f():
            for r in self.res:
                cb(res)
            return defer.succeed("yay")
        reactor.callWhenRunning(f)

class FakeCache(object):

    def get(self, x):
        return defer.succeed([0, None])

    def set(self, k, v):
        return defer.succeed(None)

class QueryRegistryTest(unittest.TestCase):

    started = 0
    stopped = 0

    def setUp(self):
        import twisted
        twisted.internet.base.DelayedCall.debug = True
        super(QueryRegistryTest, self).setUp()

        cache.mc = FakeCache()
        self.patch(scheduling.Query, '_doStart', self.trackStarted)
        self.patch(scheduling.Query, 'start', lambda *x: self.fail("unexpected start"))
        self.patch(scheduling.Query, 'stop', self.trackStopped)

        self.qr = scheduling.QueryRegistry(lambda x: FakeTwitterAPI(['a']))
        self.assertEquals(0, len(self.qr))
        self.qr.add('dustin@localhost', 'test query')

    def trackStarted(self, *args):
        self.started += 1

    def trackStopped(self, *args):
        self.stopped += 1

    def testTracking(self):
        self.assertEquals(1, len(self.qr))
        self.assertEquals(1, self.started)

    def testUntracking(self):
        self.qr.untracked('dustin@localhost', 'test query')
        self.assertEquals(0, len(self.qr))
        self.assertEquals(1, self.stopped)

    def testRemove(self):
        self.qr.add('dustin@localhost', 'test query two')
        self.assertEquals(2, len(self.qr))
        self.assertEquals(2, self.started)
        self.qr.remove('dustin@localhost')
        self.assertEquals(0, len(self.qr))
        self.assertEquals(2, self.stopped)

    def testRemoveTwo(self):
        self.qr.add('dustin2@localhost', 'test query two')
        self.assertEquals(2, len(self.qr))
        self.assertEquals(2, self.started)
        self.qr.remove('dustin@localhost')
        self.assertEquals(1, len(self.qr))
        self.assertEquals(1, self.stopped)

    def testRemoveUser(self):
        self.qr.add('dustin@localhost', 'test query two')
        self.assertEquals(2, len(self.qr))
        self.assertEquals(2, self.started)
        self.qr.remove_user('', ['dustin@localhost'])
        self.assertEquals(0, len(self.qr))
        self.assertEquals(2, self.stopped)

    def testRemoveUserTwo(self):
        self.qr.add('dustin@localhost', 'test query two')
        self.qr.add('dustin2@localhost', 'test query two')
        self.assertEquals(2, len(self.qr))
        self.assertEquals(2, self.started)
        self.qr.remove_user('', ['dustin@localhost'])
        self.assertEquals(1, len(self.qr))
        self.assertEquals(1, self.stopped)

