"""All kinds of stuff for talking to databases."""

import base64
import time

from twisted.python import log
from twisted.internet import defer, task
from twisted.enterprise import adbapi

import config
import db_base

DB_POOL = adbapi.ConnectionPool(config.CONF.get("db", "driver"),
                                *eval(config.CONF.get("db", "args", raw=True)))

def parse_time(t):
    return None

def maybe_int(t):
    if t:
        return int(t)

class User(db_base.BaseUser):

    def __init__(self, jid=None):
        super(User, self).__init__(jid)
        self._id = -1

    @staticmethod
    def by_jid(jid):
        def load_user(txn):
            txn.execute("select active, auto_post, username, password, "
                        "friend_timeline_id, direct_message_id, created_at, "
                        "status, service_jid, id "
                        "from users where jid = ?", [jid])
            u = txn.fetchall()
            if u:
                r = u[0]
                log.msg("Loading from %s" % str(r))
                user = User()
                user.jid = jid
                user.active = maybe_int(r[0]) == 1
                user.auto_post = maybe_int(r[1]) == 1
                user.username = r[2]
                user.username = r[3]
                user.friend_timeline_id = maybe_int(r[4])
                user.direct_message_id = maybe_int(r[5])
                user.created_at = parse_time(r[6])
                user.status = r[7]
                user.service_jid = r[8]
                user._id = r[9]

                txn.execute("""select query
from tracks join user_tracks on (tracks.id = user_tracks.track_id)
where user_tracks.user_id = ?""", [user._id])
                user.tracks = [t[0] for t in txn.fetchall()]

                log.msg("Loaded %s (%s)" % (user, user.active))
                return user
            else:
                return User(jid)
        return DB_POOL.runInteraction(load_user)

    def _save_in_txn(self, txn):

        active = 1 if self.active else 0

        if self._id == -1:
            txn.execute("insert into users("
                        "  jid, active, auto_post, username, password, status, "
                        "  friend_timeline_id, direct_message_id, "
                        "  service_jid, created_at )"
                        " values(?, ?, ?, ?, ?, ?, ?, ?, ?, current_timestamp)",
                        [self.jid, active, self.auto_post, self.status,
                         self.username, self.password,
                         self.friend_timeline_id,
                         self.direct_message_id, self.service_jid])

                # sqlite specific...
            txn.execute("select last_insert_rowid()")
            self._id = txn.fetchall()[0][0]
        else:
            txn.execute("update users set active=?, auto_post=?, "
                        "  username=?, password=?, status=?, "
                        "  friend_timeline_id=?, direct_message_id=?, "
                        "  service_jid = ? "
                        " where id = ?",
                        [active, self.auto_post,
                         self.username, self.password, self.status,
                         self.friend_timeline_id,
                         self.direct_message_id, self.service_jid,
                         self._id])

        # TODO:  Begin difficult process of synchronizing track lists
        txn.execute("""select user_tracks.id, query
from tracks join user_tracks on (tracks.id = user_tracks.track_id)
where user_tracks.user_id = ?""", [self._id])
        db_tracks = {}
        for i, q in txn.fetchall():
            db_tracks[q] = str(i)

        rm_ids = [db_tracks[q] for q in db_tracks.keys() if not q in self.tracks]

        # Remove track records that no longer exist.
        txn.execute("delete from user_tracks where id in (?)",
                    [', '.join(rm_ids)])

        # Add the missing tracks.
        for q in [q for q in self.tracks if not q in db_tracks]:
            txn.execute("insert into user_tracks(user_id, track_id, created_at) "
                        " values(?, ?, current_timestamp)",
                        [self._id, self._qid(txn, q)])

        return True

    def _qid(self, txn, q):
        txn.execute("select id from tracks where query = ?", [q])
        r = txn.fetchall()
        if r:
            return r[0][0]
        else:
            txn.execute("insert into tracks (query) values(?)", [q])
            txn.execute("select last_insert_rowid()")
            res = txn.fetchall()
            return res[0][0]

    def save(self):
        return DB_POOL.runInteraction(self._save_in_txn)

def initialize():
    pass

def model_counts():
    """Returns a deferred whose callback will receive a dict of object
    counts, e.g.

       {'users': n, 'tracks': m}
    """
    d = defer.Deferred()

    dbd = DB_POOL.runQuery("""select 'users', count(*) from users
union all
select 'tracks', count(*) from user_tracks""")

    def cb(rows):
        rv = {}
        for r in rows:
            rv[r[0]] = int(r[1])
        d.callback(rv)

    dbd.addCallback(cb)
    dbd.addErrback(lambda e: d.errback(e))

    return d

def get_top10(n=10):
    """Returns a deferred whose callback will receive a list of at
    most `n` (number, 'tag') pairs sorted in reverse"""

    return DB_POOL.runQuery("""select count(*), t.query as watchers
 from tracks t join user_tracks ut on (t.id = ut.track_id)
 group by t.query
 order by watchers desc, query
 limit 10""")


def get_active_users():
    """Returns a deferred whose callback will receive a list of active JIDs."""

    d = defer.Deferred()
    dbd = DB_POOL.runQuery("select jid from users where active = 1")
    dbd.addCallback(lambda res: d.callback([r[0] for r in res]))
    dbd.addErrback(lambda e: d.errback(e))

    return d
