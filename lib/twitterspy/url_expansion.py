import re

from twisted.internet import task, reactor, defer

import longurl

class Expander(object):

    def __init__(self):
        self.lu = longurl.LongUrl('twitterspy')
        self.regex = None

    def initialize(self):
        self.lu.getServices().addCallback(self._registerServices)

    def _registerServices(self, svcs):
        domains = set()
        for s in svcs.values():
            domains.update(s.domains)

        self.regex_str = "(http://(" + '|'.join(self.__fixup(d) for d in domains) + r")/\S+)"
        self.regex = re.compile(self.regex_str)

    def __fixup(self, d):
        return d.replace('.', r'\.')

    def expand(self, msg):
        rv = defer.Deferred()

        m = self.regex.search(msg)
        if m:
            u, k = m.groups()
            def gotErr(e):
                log.err(e)
                rv.callback(msg)
            def gotRes(res):
                rv.callback(msg.replace(u, "%s (from %s)" % (res, u)))
            self.lu.expand(u).addErrback(gotErr).addCallback(gotRes)
        else:
            # No match, immediately hand the message back.
            def passThrough():
                rv.callback(msg)
            reactor.callWhenRunning(passThrough)

        return rv

expander = Expander()
