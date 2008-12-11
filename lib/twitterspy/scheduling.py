from twisted.internet import task

class Query(set):

    def __init__(self, query):
        super(Query, self).__init__()
        self.query = query
        self.last_id = 0
        self.loop = task.LoopingCall(self)
        self.loop.start(15)

    def __call__(self):
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

    def remove(self, user):
        print "Removing", user
        for k in list(self.queries.keys()):
            q = self.queries[k]
            q.discard(user)
            if not q:
                q.stop()
                del self.queries[k]

queries = QueryRegistry()
