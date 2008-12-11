from twisted.internet import task

import twitter

class Query(set):

    def __init__(self, query):
        super(Query, self).__init__()
        self.query = query
        self.last_id = 0
        self.loop = task.LoopingCall(self)
        self.loop.start(15)

    def _gotResult(self, entry):
        eid = int(entry.id.split(':')[-1])
        self.last_id = max(self.last_id, eid)
        print "Result:", entry.title

    def __call__(self):
        twitter.Twitter().search(self.query,
            self._gotResult, {'since_id': str(self.last_id)})
        print "Searching", self.query

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
