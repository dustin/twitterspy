from __future__ import with_statement

import datetime
import base64

from sqlalchemy import *
from sqlalchemy.orm import sessionmaker, mapper, relation, backref, exc, join

from twitterspy import config

_engine = create_engine(config.CONF.get('general', 'db'))

_metadata = MetaData()

Session = sessionmaker()

# Adding methods to Session so it can work with a with statement
def _session_enter(self):
    return self

def _session_exit(self, *exc):
    self.close()

Session.__enter__ = _session_enter
Session.__exit__ = _session_exit
Session.configure(bind=_engine)

def wants_session(orig):
    def f(*args):
        with Session() as session:
            return orig(*args + (session,))
    return f

class User(object):

    @staticmethod
    def by_jid(jid, session=None):
        s=session
        if not s:
            s=Session()
        try:
            return s.query(User).filter_by(jid=jid).one()
        finally:
            if not session:
                s.close()

    @staticmethod
    def update_status(jid, status, session=None):
        """Find or create a user by jid and set the user's status"""
        s=session
        if not s:
            s = Session()
        try:
            u = None
            if not status:
                status="online"
            try:
                u=User.by_jid(jid, s)
            except exc.NoResultFound, e:
                u=User()
                u.jid=jid

            u.status=status
            s.add(u)
            s.commit()
            return u
        finally:
            if not session:
                s.close()

    def track(self, query, session):
        try:
            return session.query(Track).join(User.tracks).filter(
                User.id == self.id).filter(Track.query == query).one()
        except exc.NoResultFound, e:
            try:
                track = session.query(Track).filter_by(query=query).one()
            except exc.NoResultFound, e:
                track = Track()
                track.query = query
            self.tracks.append(track)

    def untrack(self, query, session):
        try:
            t = session.query(UserTrack).select_from(
                join(UserTrack, Track)).filter(
                UserTrack.user_id == self.id).filter(Track.query == query).one()
            session.delete(t)
            return True
        except exc.NoResultFound, e:
            return False

    @property
    def has_credentials(self):
        return self.username and self.password

    @property
    def decoded_password(self):
        return base64.decodestring(self.password) if self.password else None

class Track(object):
    pass

class UserTrack(object):
    pass

_users_table = Table('users', _metadata,
    Column('id', Integer, primary_key=True, index=True, unique=True),
    Column('jid', String(128), index=True, unique=True),
    Column('username', String(50)),
    Column('password', String(50)),
    Column('active', Boolean, default=True),
    Column('status', String(50)),
    Column('min_id', Integer, default=0),
    Column('language', String(2)),
    Column('auto_post', Boolean, default=False),
    Column('friend_timeline_id', Integer),
    Column('direct_message_id', Integer),
    Column('next_scan', DateTime),
    Column('created_at', DateTime, default=datetime.datetime.now)
)

_tracks_table = Table('tracks', _metadata,
    Column('id', Integer, primary_key=True, index=True, unique=True),
    Column('query', String, index=True, unique=True),
    Column('max_seen', Integer),
)

_usertrack_table = Table('user_tracks', _metadata,
    Column('id', Integer, primary_key=True, index=True),
    Column('user_id', Integer, ForeignKey('users.id')),
    Column('track_id', Integer, ForeignKey('tracks.id')),
    Column('created_at', DateTime, default=datetime.datetime.now),
)

mapper(User, _users_table, properties={
    'tracks': relation(Track, secondary=_usertrack_table, backref='tracks')
    })
mapper(UserTrack, _usertrack_table, properties={
    'user': relation(User),
    'track': relation(Track)
    })
mapper(Track, _tracks_table, properties={})
