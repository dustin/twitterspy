"""All kinds of stuff for talking to databases."""

import base64
import time

from twisted.python import log
from twisted.internet import defer

import paisley

import config

DB_NAME='twitterspy'

def get_couch():
    return paisley.CouchDB('localhost')

class User(object):

    def __init__(self, jid=None):
        self.jid = jid
        self.active = True
        self.min_id = 0
        self.auto_post = False
        self.username = None
        self.password = None
        self.status = None
        self.friend_timeline_id = None
        self.direct_message_id = None
        self.created_at = time.time()
        self._rev = None
        self.tracks = []

    @staticmethod
    def from_doc(doc):
        print "Loading from doc:", str(doc)
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
        return rv

    @staticmethod
    def by_jid(jid):
        couch = get_couch()
        d = couch.openDoc(DB_NAME, str(jid))
        rv = defer.Deferred()
        d.addCallback(lambda doc: rv.callback(User.from_doc(doc)))
        d.addErrback(lambda e: rv.callback(User(jid)))
        return rv

    def track(self, query):
        self.tracks.append(query)

    def untrack(self, query):
        self.tracks.remove(query)

    def save(self):
        return get_couch().saveDoc(DB_NAME, self.to_doc(), str(self.jid))

    @property
    def has_credentials(self):
        return self.username and self.password

    @property
    def decoded_password(self):
        return base64.decodestring(self.password) if self.password else None

    @property
    def is_admin(self):
        return self.jid in config.ADMINS

def model_counts():
    d = defer.Deferred()
    docd = get_couch().openDoc(DB_NAME, "_view/counts/counts")
    docd.addCallback(lambda r: d.callback(r['rows'][0]['value']))
    docd.addErrback(lambda e: d.errback(e))

    return d
