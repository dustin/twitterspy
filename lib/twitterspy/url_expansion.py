import re

from twisted.internet import task, reactor, defer
from twisted.python import log

import longurl

class Expander(object):

    def __init__(self):
        self.lu = longurl.LongUrl('twitterspy')
        self.regex = None

    def loadServices(self):
        def _e(e):
            log.msg("Error loading expansion rules.  Trying again in 5s")
            reactor.callLater(5, self.loadServices)
        self.lu.getServices().addCallback(self._registerServices).addErrback(_e)

    def _registerServices(self, svcs):
        domains = set()
        for s in svcs.values():
            domains.update(s.domains)

        self.regex_str = "(http://(" + '|'.join(self.__fixup(d) for d in domains) + r")/\S+)"
        self.regex = re.compile(self.regex_str)

    def __fixup(self, d):
        return d.replace('.', r'\.')

    def _e(self, u):
        return u.replace("&", "&amp;")

    def expand(self, plain, html=None):
        rv = defer.Deferred()

        m = self.regex and self.regex.search(plain)
        if m:
            u, k = m.groups()
            def gotErr(e):
                log.err(e)
                reactor.callWhenRunning(rv.callback, (plain, html))
            def gotRes(res):
                # Sometimes, the expander returns its input.  That sucks.
                if res.url == u:
                    plainSub = plain
                    htmlSub = html
                else:
                    plainSub = plain.replace(u, "%s (from %s)" % (self._e(res.url), u))
                    if html:
                        htmlSub = html.replace(u, "%s" % (self._e(res.url),))
                    else:
                        htmlSub = None
                        log.msg("rewrote %s to %s" % (plain, plainSub))
                reactor.callWhenRunning(rv.callback, (plainSub, htmlSub))
            self.lu.expand(u).addCallback(gotRes).addErrback(gotErr)
        else:
            # No match, immediately hand the message back.
            reactor.callWhenRunning(rv.callback, (plain, html))

        return rv

expander = Expander()
