import random
from collections import deque

from twisted.python import log
from twisted.internet import task, defer, reactor, threads
from twisted.words.protocols.jabber.jid import JID

import twitter
import protocol

import models

search_semaphore = defer.DeferredSemaphore(tokens=5)
private_semaphore = defer.DeferredSemaphore(tokens=20)
available_sem = defer.DeferredSemaphore(tokens=2)

# Record the 1000 most recent search results (assuming good from the beginning)
recent_results = deque([True] * 1000)

def tally_results():
    good = reduce(lambda x, y: x + 1 if y else x, recent_results)
    lrr = len(recent_results)
    percentage = float(good) / float(lrr)
    msg = "Processed %d out of %d recent searches" % (good, lrr)
    mood = ""
    if percentage > .9:
        mood = "happy"
    elif percentage > .5:
        mood = "frustrated"
    elif percentage > .1:
        mood = "annoyed"
    else:
        mood = "angry"

    print msg + " my mood is " + mood

class JidSet(set):

    def bare_jids(self):
        return set([JID(j).userhost() for j in self])

class Query(JidSet):

    loop_time = 5 * 60

    def __init__(self, query, last_id):
        super(Query, self).__init__()
        self.query = query
        self.last_id = last_id

        r=random.Random()
        then = r.randint(1, min(60, self.loop_time / 2))
        log.msg("Starting %s in %ds" % (self.query, then))
        self.loop = None
        reactor.callLater(then, self.start)

    def _save_result(self, r):
        recent_results.popleft()
        recent_results.append(r)

    def _gotResult(self, entry):
        self._save_result(True)
        eid = int(entry.id.split(':')[-1])
        self.last_id = max(self.last_id, eid)
        conn = protocol.current_conn
        u = entry.author.name.split(' ')[0]
        plain=u + ": " + entry.title
        hcontent=entry.content.replace("&lt;", "<").replace("&gt;", ">"
            ).replace('&amp;', '&')
        html="<a href='%s'>%s</a>: %s" % (entry.author.uri, u, hcontent)
        for jid in self.bare_jids():
            key = str(eid) + "@" + jid
            conn.send_html_deduped(jid, plain, html, key)

    @models.wants_session
    def _deferred_write(self, theId, session):
        t=session.query(models.Track).filter_by(query=self.query).one()
        t.max_seen = theId
        session.commit()

    def _save_track_id(self, old_id):
        def f(x):
            if old_id != self.last_id:
                threads.deferToThread(self._deferred_write, self.last_id)
        return f

    def __call__(self):
        # Don't bother if we're not connected...
        if protocol.current_conn:
            global search_semaphore
            search_semaphore.run(self._do_search)

    def _reportError(self, e):
        log.msg("Error in search %s: %s" % (self.query, str(e)))
        self._save_result(False)

    def _do_search(self):
        log.msg("Searching %s" % self.query)
        params = {}
        if self.last_id > 0:
            params['since_id'] = str(self.last_id)
        return twitter.Twitter().search(self.query, self._gotResult, params
            ).addCallback(self._save_track_id(self.last_id)).addErrback(
            self._reportError)

    def start(self):
        self.loop = task.LoopingCall(self)
        self.loop.start(self.loop_time)

    def stop(self):
        log.msg("Stopping query %s" % self.query)
        if self.loop:
            self.loop.stop()
            self.loop = None

class QueryRegistry(object):

    def __init__(self):
        self.queries = {}

    def add(self, user, query_str, last_id):
        log.msg("Adding %s: %s" % (user, query_str))
        if not self.queries.has_key(query_str):
            self.queries[query_str] = Query(query_str, last_id)
        self.queries[query_str].add(user)

    def untracked(self, user, query):
        q = self.queries.get(query)
        if q:
            q.discard(user)
            if not q:
                q.stop()
                del self.queries[query]

    def remove(self, user):
        log.msg("Removing %s" % user)
        for k in list(self.queries.keys()):
            self.untracked(user, k)

    def remove_user(self, user, jids):
        for k in list(self.queries.keys()):
            for j in jids:
                self.untracked(j, k)

class UserStuff(JidSet):

    loop_time = 90

    def __init__(self, short_jid, friends_id, dm_id):
        super(UserStuff, self).__init__()
        self.short_jid = short_jid
        self.last_friend_id = friends_id
        self.last_dm_id = dm_id

        self.username = None
        self.password = None
        self.loop = None

    def _deliver_message(self, type, entry):
        s = getattr(entry, 'sender', None)
        if not s:
            s=entry.user
        u = s.screen_name
        plain="[%s] %s: %s" % (type, u, entry.text)
        aurl = "http://twitter.com/" + u
        html="[%s] <a href='%s'>%s</a>: %s" % (type, aurl, u, entry.text)
        conn = protocol.current_conn
        for jid in self.bare_jids():
            key = str(entry.id) + "@" + jid
            conn.send_html_deduped(jid, plain, html, key)

    def _gotDMResult(self, entry):
        self.last_dm_id = max(self.last_dm_id, int(entry.id))
        self._deliver_message('direct', entry)

    def _gotFriendsResult(self, entry):
        self.last_friend_id = max(self.last_friend_id, int(entry.id))
        self._deliver_message('friend', entry)

    @models.wants_session
    def _deferred_write(self, jid, mprop, new_val, session):
        u = models.User.by_jid(jid, session)
        setattr(u, mprop, new_val)
        session.commit()

    def _maybe_update_prop(self, prop, mprop):
        old_val = getattr(self, prop)
        def f(x):
            new_val = getattr(self, prop)
            if old_val != new_val:
                threads.deferToThread(
                    self._deferred_write, self.short_jid, mprop, new_val)
        return f

    def __call__(self):
        if self.username and self.password and protocol.current_conn:
            global private_semaphore
            private_semaphore.run(self._get_user_stuff)

    def _reportError(self, e):
        log.msg("Error getting user data for %s: %s" % (self.short_jid, str(e)))

    def _get_user_stuff(self):
        log.msg("Getting privates for %s" % self.short_jid)
        params = {}
        if self.last_dm_id > 0:
            params['since_id'] = str(self.last_dm_id)
        tw = twitter.Twitter(self.username, self.password)
        tw.direct_messages(self._gotDMResult, params).addCallback(
            self._maybe_update_prop('last_dm_id', 'direct_message_id')
            ).addErrback(self._reportError)

        if self.last_friend_id is not None:
            tw.friends(self._gotFriendsResult,
                {'since_id': str(self.last_friend_id)}).addCallback(
                    self._maybe_update_prop(
                        'last_friend_id', 'friend_timeline_id')
                ).addErrback(self._reportError)

    def start(self):
        log.msg("Starting %s" % self.short_jid)
        self.loop = task.LoopingCall(self)
        self.loop.start(self.loop_time)

    def stop(self):
        if self.loop:
            log.msg("Stopping user %s" % self.short_jid)
            self.loop.stop()
            self.loop = None

class UserRegistry(object):

    def __init__(self):
        self.users = {}

    def add(self, short_jid, full_jid, friends_id, dm_id):
        log.msg("Adding %s as %s" % (short_jid, full_jid))
        if not self.users.has_key(short_jid):
            self.users[short_jid] = UserStuff(short_jid, friends_id, dm_id)
        self.users[short_jid].add(full_jid)

    def set_creds(self, short_jid, un, pw):
        u=self.users.get(short_jid)
        if u:
            u.username = un
            u.password = pw
            available = un and pw
            if available and not u.loop:
                u.start()
            elif u.loop and not available:
                u.stop()
        else:
            log.msg("Couldn't find %s to set creds" % short_jid)

    def remove(self, short_jid, full_jid=None):
        q = self.users.get(short_jid)
        if not q:
            return
        q.discard(full_jid)
        if not q:
            q.stop()
            del self.users[short_jid]

queries = QueryRegistry()
users = UserRegistry()

def _entity_to_jid(entity):
    return entity if isinstance(entity, basestring) else entity.userhost()

@models.wants_session
def _load_user(entity, session):
    u = models.User.update_status(_entity_to_jid(entity), None, session)
    rv = None
    if u.active:
        tracks = [(t.query, t.max_seen) for t in u.tracks]
        rv = ((u.username, u.decoded_password,
            u.friend_timeline_id, u.direct_message_id), tracks)
    return rv

def _init_user(stuff, short_jid, full_jids):
    if stuff:
        for j in full_jids:
            users.add(short_jid, j, stuff[0][2], stuff[0][3])
            for q, id in stuff[1]:
                queries.add(j, q, id)
        users.set_creds(short_jid, stuff[0][0], stuff[0][1])

def enable_user(jid):
    def process():
        return threads.deferToThread(_load_user, jid).addCallback(
            _init_user, jid, users.users.get(jid, []))
    global available_sem
    available_sem.run(process)

def disable_user(jid):
    queries.remove_user(jid, users.users.get(jid, []))
    users.set_creds(jid, None, None)

def available_user(entity):
    def process():
        return threads.deferToThread(_load_user, entity).addCallback(
            _init_user, entity.userhost(), [entity.full()])
    global available_sem
    available_sem.run(process)

def unavailable_user(entity):
    queries.remove(entity.full())
    users.remove(entity.userhost(), entity.full())

def _reset_all():
    global queries
    global users
    for q in queries.queries.values():
        q.clear()
        q.stop()
    for u in users.users.values():
        u.clear()
        u.stop()
    queries = QueryRegistry()
    users = UserRegistry()

def connected():
    _reset_all()

def disconnected():
    _reset_all()
