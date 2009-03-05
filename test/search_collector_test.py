from __future__ import with_statement

import sys
import xml

from twisted.trial import unittest
from twisted.internet import defer, reactor

sys.path.extend(['lib', '../lib',
                 'lib/twitterspy', '../lib/twitterspy',
                 'lib/twisted-longurl/lib', '../lib/twisted-longurl/lib'])

import search_collector, url_expansion

class FakeAuthor(object):

    def __init__(self, name, uri):
        self.name = name
        self.uri = uri

class FakeEntry(object):

    def __init__(self, i, author, title, content):
        self.id = i
        self.author = author
        self.title = title
        self.content = content

class FakeUrlExpander(object):

    def __init__(self):
        self.expectations = set()

    def instantError(self, plain, html):
        rv = defer.Deferred()
        reactor.callWhenRunning(rv.errback, RuntimeError("failed " + plain))
        return rv

    def instantSuccess(self, plain, html):
        rv = defer.Deferred()
        reactor.callWhenRunning(rv.callback, (plain + " m", html + " m"))
        return rv

    def expand(self, plain, html):
        if plain in self.expectations:
            return self.instantSuccess(plain, html)
        else:
            return self.instantError(plain, html)

class SearchCollectorTest(unittest.TestCase):

    def setUp(self):
        url_expansion.expander = FakeUrlExpander()

    def doSomeStuff(self, sc):
        sc.gotResult(FakeEntry('blah:14',
                               FakeAuthor('dustin author', 'http://w/'),
                               'Some Title 14',
                               'Some Content 14'))

        sc.gotResult(FakeEntry('blah:11',
                               FakeAuthor('dustin author', 'http://w/'),
                               'Some Title 11',
                               'Some Content 11'))

        sc.gotResult(FakeEntry('blah:13',
                               FakeAuthor('dustin author', 'http://w/'),
                               'Some Title 13',
                               'Some Content 13'))

    def testSimpleNoMatches(self):
        sc = search_collector.SearchCollector()
        self.doSomeStuff(sc)

        self.assertEquals(3, len(sc.deferreds))
        dl = defer.DeferredList(sc.deferreds)

        def verify(r):
            self.assertEquals([11, 13, 14], [e[0] for e in sc.results])
            self.assertEquals("dustin: Some Title 11", sc.results[0][1])
            self.flushLoggedErrors(RuntimeError)

        dl.addCallback(verify)

        return dl

    def testSomeMatches(self):
        url_expansion.expander.expectations.add('dustin: Some Title 11')
        sc = search_collector.SearchCollector()
        self.doSomeStuff(sc)

        self.assertEquals(3, len(sc.deferreds))
        dl = defer.DeferredList(sc.deferreds)

        def verify(r):
            self.assertEquals([11, 13, 14], [e[0] for e in sc.results])
            self.assertEquals("dustin: Some Title 11 m", sc.results[0][1])
            self.assertEquals("dustin: Some Title 13", sc.results[1][1])
            self.flushLoggedErrors(RuntimeError)

        dl.addCallback(verify)

        return dl
