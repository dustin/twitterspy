from twisted.internet import task

import twitter
import protocol

class Query(set):

    loop_time = 15 * 60

    def __init__(self, query):
        super(Query, self).__init__()
        self.query = query
        self.last_id = 0
        self.loop = task.LoopingCall(self)
        self.loop.start(self.loop_time)

    def _gotResult(self, entry):
        eid = int(entry.id.split(':')[-1])
        self.last_id = max(self.last_id, eid)
        print "Result:", entry.title
        conn = protocol.current_conn
        u = entry.author.name.split(' ')[0]
        plain=u + ": " + entry.title
        hcontent=entry.content.replace("&lt;", "<").replace("&gt;", ">")
        html="<a href='%s'>%s</a>: %s" % (entry.author.uri, u, hcontent)
        for jid in self:
            conn.send_html(jid, plain, html)

    def __call__(self):
        # Don't bother if we're not connected...
        if protocol.current_conn:
            print "Searching", self.query
            params = {}
            if self.last_id > 0:
                params['since_id'] = str(self.last_id)
            twitter.Twitter().search(self.query, self._gotResult, params)

    def stop(self):
        print "Stopping", self.query
        self.loop.stop()

class QueryRegistry(object):

    def __init__(self):
        self.queries = {}

    def add(self, user, query_str):
        print "Adding", user, ":", query_str
        if not self.queries.has_key(query_str):
            self.queries[query_str] = Query(query_str)
        self.queries[query_str].add(user)

    def untracked(self, user, query):
        q = self.queries[query]
        q.discard(user)
        if not q:
            q.stop()
            del self.queries[query]

    def remove(self, user):
        print "Removing", user
        for k in list(self.queries.keys()):
            self.untracked(user, k)

queries = QueryRegistry()
