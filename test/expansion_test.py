#!/usr/bin/env python

from __future__ import with_statement

import sys
import xml

from twisted.trial import unittest
from twisted.internet import defer, reactor

sys.path.extend(['lib', '../lib',
                 'lib/twitterspy', '../lib/twitterspy',
                 'lib/twisted-longurl/lib', '../lib/twisted-longurl/lib'])

import url_expansion

class SimpleService(object):

    def __init__(self, name, domains=None):
        self.name = name
        if domains:
            self.domains = domains
        else:
            self.domains = [name]

class FakeHTTP(object):

    def __init__(self):
        self.d = defer.Deferred()

    def getPage(self, *args, **kwargs):
        return self.d

class Result(object):

    def __init__(self, t, u):
        self.title = t
        self.url = u

class FakeLongUrl(object):

    def __init__(self, r):
        self.result = r

    def expand(self, u):
        rv = defer.Deferred()

        if self.result:
            reactor.callWhenRunning(rv.callback, self.result)
        else:
            reactor.callWhenRunning(rv.errback, RuntimeError("http failed"))
        return rv

class MatcherTest(unittest.TestCase):

    def setUp(self):
        self.expander = url_expansion.Expander()
        self.expander._registerServices({'is.gd':
                                             SimpleService('is.gd'),
                                         'bit.ly':
                                             SimpleService('bit.ly',
                                                           ['bit.ly', 'bit.ley'])})

    def testNoopExpansion(self):
        d = self.expander.expand("test message")
        def v(r):
            self.assertEquals('test message', r[0])
            self.assertEquals(None, r[1])
        d.addCallback(v)
        return d

    def testExpansion(self):
        self.expander.lu = FakeLongUrl(Result('Test Title', 'http://w/'))

        d = self.expander.expand("test http://is.gd/whatever message")
        def v(r):
            self.assertEquals('test http://w/ (from http://is.gd/whatever) message', r[0])
            self.assertEquals(None, r[1])
        d.addCallback(v)
        return d

    def testFailedExpansion(self):
        self.expander.lu = FakeLongUrl(None)

        def v(r):
            self.assertEquals('test http://is.gd/whatever message', r[0])
            self.assertEquals(None, r[1])
            self.flushLoggedErrors(RuntimeError)
        def h(e):
            self.fail("Error bubbled up.")
        d = self.expander.expand("test http://is.gd/whatever message")
        d.addCallback(v)
        d.addErrback(h)
        return d

    def testHtmlExpansion(self):
        self.expander.lu = FakeLongUrl(Result('Test Title', 'http://w/'))

        d = self.expander.expand("test http://is.gd/whatever message",
                                 """test <a href="http://is.gd/whatever">"""
                                 """http://is.gd/whatever</a> message""")
        def v(r):
            self.assertEquals('test http://w/ (from http://is.gd/whatever) message', r[0])
            self.assertEquals("""test <a href="http://w/">"""
                              """http://w/</a> message""", r[1])
        d.addCallback(v)
        return d
