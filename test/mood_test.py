#!/usr/bin/env python

import sys

from twisted.trial import unittest
from twisted.internet import defer, reactor
from twisted.python import failure
from twisted import web

sys.path.extend(['lib', '../lib',
                 'lib/twitterspy', '../lib/twitterspy',
                 'lib/twitty-twister/twittytwister', '../lib/twitty-twister',
                 'lib/twisted-longurl/lib', '../lib/twisted-longurl',
                 'lib/wokkel', '../lib/wokkel'])

import moodiness

def webError(n):
    return failure.Failure(web.error.Error(n))

class MoodiTest(unittest.TestCase):

    def setUp(self):
        self.m = moodiness.Moodiness()

        for i in range(25):
            self.m.markSuccess("ignored")
        for i in range(25):
            self.m.markFailure("not an exception")
        for i in range(50):
            self.m.markFailure(webError('503'))

    def testMoodCounts(self):
        h = self.m.result_counts()
        self.assertEquals(25, h[True])
        self.assertEquals(25, h[False])
        self.assertEquals(50, h['503'])

    def testMood(self):
        mood, good, total, percentage = self.m.current_mood()
        self.assertTrue(mood in ('annoyed', 'dismayed', 'depressed', 'worried'))
        self.assertEquals(25, good)
        self.assertEquals(100, total)
        self.assertEquals(0.25, percentage)


    def testWeirdFailure(self):
        r = ['503', '503', '503', '503',
        '503', '503', '503', '503', '503', '503', '503', '503', '503',
        '503', '503', '503', '503', True, '503', '503', '503', '503',
        '503', '503', '503', '503', '503', '503', '503', '503', '503',
        True, True, True, True, True, True, True, True, True, True,
        True, True, True, True, '400', True, True, True, True, True,
        True, True, True, True, True, True, True, True, True, True,
        True, True, True, True, True, True, True, True, True, True,
        True, True, True, True, True, True, True]

        self.m = moodiness.Moodiness()
        self.m.recent_results = r

        mood, good, total, percentage = self.m.current_mood()
        self.assertTrue(mood in ('frustrated', 'annoyed', 'anxious', 'grumpy'))
        self.assertEquals(47, good)
        self.assertEquals(78, total)
        self.assertAlmostEquals(0.60, percentage, .01)
