import bisect

from twisted.python import log

import url_expansion

class SearchCollector(object):

    def __init__(self, last_id=0):
        self.results=[]
        self.last_id = last_id
        self.deferreds = []

    def gotResult(self, entry):
        eid = int(entry.id.split(':')[-1])
        self.last_id = max(self.last_id, eid)
        u = entry.author.name.split(' ')[0]
        plain=u + ": " + entry.title
        hcontent=entry.content.replace("&lt;", "<"
                                       ).replace("&gt;", ">"
                                       ).replace('&amp;', '&')
        html="<a href='%s'>%s</a>: %s" % (entry.author.uri, u, hcontent)
        def errHandler(e):
            log.err(e)
            return plain, html
        def saveResults(t):
            p, h = t
            bisect.insort(self.results, (eid, p, h))
        d = url_expansion.expander.expand(plain, html).addErrback(
            errHandler).addCallback(saveResults)
        self.deferreds.append(d)
