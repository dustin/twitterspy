#!/usr/bin/env python

import sys

from twisted.trial import unittest
from twisted.internet import defer, reactor
from twisted.python import failure
from twisted import web

sys.path.extend(['lib', '../lib',
                 'lib/twitterspy', '../lib/twitterspy',
                 'lib/twitty-twister/lib', '../lib/twitty-twister',
                 'lib/wokkel', '../lib/wokkel'])

import moodiness

def webError(n):
    return failure.Failure(web.error.Error(503))

class MoodiTest(unittest.TestCase):

    def setUp(self):
        self.m = moodiness.Moodiness()

        for i in range(25):
            self.m.markSuccess("ignored")
        for i in range(25):
            self.m.markFailure("not an exception")
        for i in range(50):
            self.m.markFailure(webError(503))

    def testMoodCounts(self):
        h = self.m.result_counts()
        self.assertEquals(25, h[True])
        self.assertEquals(25, h[False])
        self.assertEquals(50, h[503])

    def testMood(self):
        mood, good, total, percentage = self.m.current_mood()
        self.assertTrue(mood in ('annoyed', 'dismayed', 'depressed', 'worried'))
        self.assertEquals(25, good)
        self.assertEquals(100, total)
        self.assertEquals(0.25, percentage)
