import re

from twisted.internet import task, reactor, defer
from twisted.python import log

import longurl

class BasicUrl(object):

    def __init__(self, title, url):
        self.title = title
        self.url = url

class Expander(object):

    cache = True

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
            self._expand(u).addCallback(gotRes).addErrback(gotErr)
        else:
            # No match, immediately hand the message back.
            reactor.callWhenRunning(rv.callback, (plain, html))

        return rv

    def _cached_lookup(self, u, mc):
        rv = defer.Deferred()

        def identity(ignored_param):
            rv.callback(BasicUrl(None, u))

        def mc_res(res):
            if res[1]:
                rv.callback(BasicUrl(None, res[1]))
            else:
                def save_res(lu_res):
                    if lu_res:
                        mc.set(u, lu_res.url.encode('utf-8'))
                        rv.callback(BasicUrl(None, lu_res.url))
                    else:
                        log.msg("No response found for %s" % u)
                        rv.callback(BasicUrl(None, u))
                self.lu.expand(u).addErrback(identity).addCallback(save_res)

        mc.get(u).addCallback(mc_res).addErrback(identity)

        return rv

    def _expand(self, u):
        if self.cache:
            import protocol
            if protocol.mc:
                return self._cached_lookup(u.encode('utf-8'), protocol.mc)
            else:
                return self.lu.expand(u)
        else:
            return self.lu.expand(u)

expander = Expander()
