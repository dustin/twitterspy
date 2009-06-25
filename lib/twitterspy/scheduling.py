import bisect
import random
import hashlib

from twisted.python import log
from twisted.internet import task, defer, reactor, threads
from twisted.words.protocols.jabber.jid import JID
from twisted.web import error

import twitter
import protocol

import db
import moodiness
import cache
import config
import search_collector

search_semaphore = defer.DeferredSemaphore(tokens=5)
private_semaphore = defer.DeferredSemaphore(tokens=20)
available_sem = defer.DeferredSemaphore(tokens=1)

MAX_REQUESTS = 20000
REQUEST_PERIOD = 3600

QUERY_FREQUENCY = 15 * 60
USER_FREQUENCY = 3 * 60

available_requests = MAX_REQUESTS
reported_empty = False
empty_resets = 0

def getTwitterAPI(*args):
    global available_requests, reported_empty
    if available_requests > 0:
        available_requests -= 1
        return twitter.Twitter(*args)
    else:
        if not reported_empty:
            reported_empty = True
            for conn in protocol.presence_conns.values():
                conn.update_presence()
        log.msg("Out of requests.  :(")
        # Return something that just generates deferreds that error.
        class ErrorGenerator(object):
            def __getattr__(self, attr):
                def error_generator(*args):
                    return defer.fail(
                        "There are no more available twitter requests.")
                return error_generator
        return ErrorGenerator()

def resetRequests():
    global available_requests, empty_resets, reported_empty
    if available_requests == 0:
        empty_resets += 1
        reported_empty = False
    available_requests = MAX_REQUESTS
    for conn in protocol.presence_conns.values():
        conn.update_presence()
    log.msg("Available requests are reset to %d" % available_requests)

class JidSet(set):

    def bare_jids(self):
        return set([JID(j).userhost() for j in self])

class Query(JidSet):

    loop_time = QUERY_FREQUENCY

    def __init__(self, query, last_id=0, getAPI=getTwitterAPI):
        super(Query, self).__init__()
        self.getAPI = getAPI
        self.query = query
        self.cache_key = self._compute_cache_key(query)
        self.loop = None

        cache.mc.get(self.cache_key).addCallback(self._doStart)

    def _compute_cache_key(self, query):
        return hashlib.md5(query.encode('utf-8')).hexdigest()

    def _doStart(self, res):
        if res[1]:
            self.last_id = res[1]
            log.msg("Loaded last ID for %s from memcache: %s"
                     % (self.query, self.last_id))
        else:
            log.msg("No last ID for %s" % (self.query,))
            self.last_id = 0
        r=random.Random()
        then = r.randint(1, min(60, self.loop_time / 2))
        log.msg("Starting %s in %ds" % (self.query, then))
        reactor.callLater(then, self.start)

    def _sendMessages(self, something, results):
        first_shot = self.last_id == 0
        self.last_id = results.last_id
        if not first_shot:
            def send(r):
                for eid, plain, html in results.results:
                    for jid in self.bare_jids():
                        key = str(eid) + "@" + jid
                        protocol.send_html_deduped(jid, plain, html, key)
            dl = defer.DeferredList(results.deferreds)
            dl.addCallback(send)

    def __call__(self):
        # Don't bother if we're not connected...
        if protocol.current_conns:
            global search_semaphore
            search_semaphore.run(self._do_search)

    def _reportError(self, e):
        log.msg("Error in search %s: %s" % (self.query, str(e)))

    def _save_track_id(self, x, old_id):
        if old_id != self.last_id:
            cache.mc.set(self.cache_key, str(self.last_id))

    def _do_search(self):
        log.msg("Searching %s" % self.query)
        params = {}
        if self.last_id > 0:
            params['since_id'] = str(self.last_id)
        results=search_collector.SearchCollector(self.last_id)
        return self.getAPI().search(self.query, results.gotResult,
            params
            ).addCallback(moodiness.moodiness.markSuccess
            ).addErrback(moodiness.moodiness.markFailure
            ).addCallback(self._sendMessages, results
            ).addCallback(self._save_track_id, self.last_id
            ).addErrback(self._reportError)

    def start(self):
        self.loop = task.LoopingCall(self)
        self.loop.start(self.loop_time)

    def stop(self):
        log.msg("Stopping query %s" % self.query)
        if self.loop:
            self.loop.stop()
            self.loop = None

class QueryRegistry(object):

    def __init__(self, getAPI=getTwitterAPI):
        self.queries = {}
        self.getAPI = getAPI

    def add(self, user, query_str, last_id=0):
        log.msg("Adding %s: %s" % (user, query_str))
        if not self.queries.has_key(query_str):
            self.queries[query_str] = Query(query_str, last_id, self.getAPI)
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

    def __len__(self):
        return len(self.queries)

class UserStuff(JidSet):

    loop_time = USER_FREQUENCY

    def __init__(self, short_jid, friends_id, dm_id):
        super(UserStuff, self).__init__()
        self.short_jid = short_jid
        self.last_friend_id = friends_id
        self.last_dm_id = dm_id

        self.username = None
        self.password = None
        self.loop = None

    def _format_message(self, type, entry, results):
        s = getattr(entry, 'sender', None)
        if not s:
            s=entry.user
        u = s.screen_name
        plain="[%s] %s: %s" % (type, u, entry.text)
        aurl = "https://twitter.com/" + u
        htype = '<b>' + type + '</b>'
        html="[%s] <a href='%s'>%s</a>: %s" % (htype, aurl, u, entry.text)
        bisect.insort(results, (entry.id, plain, html))

    def _deliver_messages(self, whatever, messages):
        for eid, plain, html in messages:
            for jid in self.bare_jids():
                key = str(eid) + "@" + jid
                protocol.send_html_deduped(jid, plain, html, key)

    def _gotDMResult(self, results):
        def f(entry):
            self.last_dm_id = max(self.last_dm_id, int(entry.id))
            self._format_message('direct', entry, results)
        return f

    def _gotFriendsResult(self, results):
        def f(entry):
            self.last_friend_id = max(self.last_friend_id, int(entry.id))
            self._format_message('friend', entry, results)
        return f

    def _deferred_write(self, u, mprop, new_val):
        setattr(u, mprop, new_val)
        u.save()

    def _maybe_update_prop(self, prop, mprop):
        old_val = getattr(self, prop)
        def f(x):
            new_val = getattr(self, prop)
            if old_val != new_val:
                db.User.by_jid(self.short_jid).addCallback(self._deferred_write,
                                                           mprop, new_val)
        return f

    def __call__(self):
        if self.username and self.password and protocol.current_conns:
            global private_semaphore
            private_semaphore.run(self._get_user_stuff)

    def _cleanup401s(self, e):
        e.trap(error.Error)
        if int(e.value.status) == 401:
            log.msg("Error 401 getting user data for %s, disabling"
                    % self.short_jid)
            self.stop()
        else:
            log.msg("Unknown http error:  %s: %s" % (e.value.status, str(e)))

    def _reportError(self, e):
        log.msg("Error getting user data for %s: %s" % (self.short_jid, str(e)))

    def _get_user_stuff(self):
        log.msg("Getting privates for %s" % self.short_jid)
        params = {}
        if self.last_dm_id > 0:
            params['since_id'] = str(self.last_dm_id)
        tw = getTwitterAPI(self.username, self.password)
        dm_list=[]
        tw.direct_messages(self._gotDMResult(dm_list), params).addCallback(
            self._maybe_update_prop('last_dm_id', 'direct_message_id')
            ).addCallback(self._deliver_messages, dm_list
            ).addErrback(self._cleanup401s).addErrback(self._reportError)

        if self.last_friend_id is not None:
            friend_list=[]
            tw.friends(self._gotFriendsResult(friend_list),
                {'since_id': str(self.last_friend_id)}).addCallback(
                    self._maybe_update_prop(
                        'last_friend_id', 'friend_timeline_id')
                ).addCallback(self._deliver_messages, friend_list
                ).addErrback(self._cleanup401s).addErrback(self._reportError)

    def start(self):
        log.msg("Starting %s" % self.short_jid)
        self.loop = task.LoopingCall(self)
        self.loop.start(self.loop_time, now=False)

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

    def __len__(self):
        return len(self.users)

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

def __init_user(entity, jids=[]):
    jid = _entity_to_jid(entity)
    def f(u):
        if u.active:
            full_jids = users.users.get(jid, jids)
            for j in full_jids:
                users.add(jid, j, u.friend_timeline_id, u.direct_message_id)
                for q in u.tracks:
                    queries.add(j, q)
            users.set_creds(jid, u.username, u.decoded_password)
    db.User.by_jid(jid).addCallback(f)

def enable_user(jid):
    global available_sem
    available_sem.run(__init_user, jid)

def disable_user(jid):
    queries.remove_user(jid, users.users.get(jid, []))
    users.set_creds(jid, None, None)

def available_user(entity):
    global available_sem
    available_sem.run(__init_user, entity, [entity.full()])

def unavailable_user(entity):
    queries.remove(entity.full())
    users.remove(entity.userhost(), entity.full())

def resources(jid):
    """Find all watched resources for the given JID."""
    jids=users.users.get(jid, [])
    return [JID(j).resource for j in jids]

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
    # _reset_all()
    pass

def disconnected():
    # _reset_all()
    pass
