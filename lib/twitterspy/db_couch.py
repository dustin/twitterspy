"""All kinds of stuff for talking to databases."""

import time

from twisted.python import log
from twisted.internet import defer, task

import paisley

import config
import db_base

DB_NAME='twitterspy'

def get_couch():
    return paisley.CouchDB(config.CONF.get('db', 'host'))

class User(db_base.BaseUser):

    @staticmethod
    def from_doc(doc):
        user = User()
        user.jid = doc['_id']
        v = doc
        user.active = v.get('active')
        user.auto_post = v.get('auto_post')
        user.username = v.get('username')
        user.password = v.get('password')
        user.status = v.get('status')
        user.friend_timeline_id = v.get('friend_timeline_id')
        user.direct_message_id = v.get('direct_message_id')
        user.created_at = v.get('created_at', time.time())
        user._rev = v.get('_rev')
        user.tracks = v.get('tracks', [])
        return user

    def to_doc(self):
        rv = dict(self.__dict__)
        rv['doctype'] = 'User'
        for k in [k for k,v in rv.items() if not v]:
            del rv[k]
        # Don't need two copies of the jids.
        del rv['jid']
        return rv

    @staticmethod
    def by_jid(jid):
        couch = get_couch()
        d = couch.openDoc(DB_NAME, str(jid))
        rv = defer.Deferred()
        d.addCallback(lambda doc: rv.callback(User.from_doc(doc)))
        d.addErrback(lambda e: rv.callback(User(jid)))
        return rv

    def save(self):
        return get_couch().saveDoc(DB_NAME, self.to_doc(), str(self.jid))

def initialize():
    def periodic():
        log.msg("Performing compaction.")
        get_couch().post("/" + DB_NAME + '/_compact', '')
    loop = task.LoopingCall(periodic)
    loop.start(3600, now=False)

def model_counts():
    """Returns a deferred whose callback will receive a dict of object
    counts, e.g.

       {'users': n, 'tracks': m}
    """
    d = defer.Deferred()
    docd = get_couch().openView(DB_NAME, "counts", "counts")
    docd.addCallback(lambda r: d.callback(r['rows'][0]['value']))
    docd.addErrback(lambda e: d.errback(e))

    return d

def get_top10(n=10):
    """Returns a deferred whose callback will receive a list of at
    most `n` (number, 'tag') pairs sorted in reverse"""
    d = defer.Deferred()
    docd = get_couch().openView(DB_NAME, "query_counts", "query_counts",
                                group="true")
    def processResults(resp):
        rows = sorted([(r['value'], r['key']) for r in resp['rows']],
                      reverse=True)
        d.callback(rows[:n])
    docd.addCallback(processResults)
    docd.addErrback(lambda e: d.errback(e))
    return d

def get_active_users():
    """Returns a deferred whose callback will receive a list of active JIDs."""
    d = defer.Deferred()
    docd = get_couch().openView(DB_NAME, "users", "active")
    docd.addCallback(lambda res: d.callback([r['value'] for r in res['rows']]))
    docd.addErrback(lambda e: d.errback(e))
    return d
