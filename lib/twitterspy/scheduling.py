from twisted.internet import task

import twitter
import protocol

import models

class Query(set):

    loop_time = 15 * 60

    def __init__(self, query, last_id):
        super(Query, self).__init__()
        self.query = query
        self.last_id = last_id
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
            key = jid + "@" + str(eid)
            conn.send_html_deduped(jid, plain, html, key)

    def _save_track_id(self, old_id):
        def f(x):
            if old_id != self.last_id:
                session = models.Session()
                try:
                    t=session.query(models.Track).filter_by(
                        query=self.query).one()
                    t.max_seen = self.last_id
                    session.commit()
                finally:
                    session.close()
        return f

    def __call__(self):
        # Don't bother if we're not connected...
        if protocol.current_conn:
            print "Searching", self.query
            params = {}
            if self.last_id > 0:
                params['since_id'] = str(self.last_id)
            twitter.Twitter().search(self.query, self._gotResult, params
                ).addCallback(self._save_track_id(self.last_id))

    def stop(self):
        print "Stopping", self.query
        self.loop.stop()

class QueryRegistry(object):

    def __init__(self):
        self.queries = {}

    def add(self, user, query_str, last_id):
        print "Adding", user, ":", query_str
        if not self.queries.has_key(query_str):
            self.queries[query_str] = Query(query_str, last_id)
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

class UserStuff(set):

    loop_time = 2 * 60

    def __init__(self, short_jid, username, password, friends_id, dm_id):
        super(UserStuff, self).__init__()
        self.short_jid = short_jid
        self.username = username
        self.password = password
        self.last_friend_id = friends_id

        self.last_dm_id = dm_id
        self.loop = task.LoopingCall(self)
        self.loop.start(self.loop_time)

    def _deliver_message(self, type, entry):
        s = getattr(entry, 'sender', None)
        if not s:
            s=entry.user
        u = s.screen_name
        plain="[%s] %s: %s" % (type, u, entry.text)
        aurl = "http://twitter.com/" + u
        html="[%s] <a href='%s'>%s</a>: %s" % (type, aurl, u, entry.text)
        conn = protocol.current_conn
        for jid in self:
            key = jid + "@" + str(entry.id)
            conn.send_html_deduped(jid, plain, html, key)

    def _gotDMResult(self, entry):
        self.last_dm_id = max(self.last_dm_id, int(entry.id))
        self._deliver_message('direct', entry)

    def _gotFriendsResult(self, entry):
        self.last_friend_id = max(self.last_friend_id, int(entry.id))
        self._deliver_message('friend', entry)

    def _maybe_update_prop(self, prop, mprop):
        old_val = getattr(self, prop)
        def f(x):
            new_val = getattr(self, prop)
            if old_val != new_val:
                session = models.Session()
                try:
                    u = models.User.by_jid(self.short_jid, session)
                    setattr(u, mprop, new_val)
                    session.add(u)
                    session.commit()
                finally:
                    session.close()
        return f

    def __call__(self):
        if self.username and self.password and protocol.current_conn:
            print "Getting privates for", self.short_jid
            params = {}
            if self.last_dm_id > 0:
                params['since_id'] = str(self.last_dm_id)
            tw = twitter.Twitter(self.username, self.password)
            tw.direct_messages(self._gotDMResult, params).addCallback(
                self._maybe_update_prop('last_dm_id', 'direct_message_id'))

            if self.last_friend_id is not None:
                tw.friends(self._gotFriendsResult,
                    {'since_id': str(self.last_friend_id)}).addCallback(
                        self._maybe_update_prop(
                            'last_friend_id', 'friend_timeline_id'))

    def stop(self):
        print "Stopping", self.short_jid
        self.loop.stop()

class UserRegistry(object):

    def __init__(self):
        self.users = {}

    def add(self, short_jid, full_jid, un, pw, friends_id, dm_id):
        print "Adding %s as %s" % (short_jid, full_jid)
        if not self.users.has_key(short_jid):
            self.users[short_jid] = UserStuff(short_jid, un, pw,
                friends_id, dm_id)
        self.users[short_jid].add(full_jid)

    def remove(self, short_jid, full_jid):
        q = self.users[short_jid]
        q.discard(full_jid)
        if not q:
            q.stop()
            del self.users[short_jid]

queries = QueryRegistry()
users = UserRegistry()
