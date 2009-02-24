import time
import base64

import config

class BaseUser(object):

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

    def __repr__(self):
        return "<User %s with %d tracks>" % (self.jid, len(self.tracks))

    def track(self, query):
        self.tracks.append(query)

    def untrack(self, query):
        try:
            self.tracks.remove(query)
            return True
        except ValueError:
            return False

    @property
    def has_credentials(self):
        return self.username and self.password

    @property
    def decoded_password(self):
        return base64.decodestring(self.password) if self.password else None

    @property
    def is_admin(self):
        return self.jid in config.ADMINS

