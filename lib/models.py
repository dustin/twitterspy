import datetime

from sqlalchemy import *
from sqlalchemy.orm import sessionmaker, mapper, relation, backref, exc, join

from twitterspy import config

_engine = create_engine(config.CONF.get('general', 'db'))

_metadata = MetaData()

Session = sessionmaker()
Session.configure(bind=_engine)

class User(object):

    @staticmethod
    def by_jid(jid, session=None):
        s=session
        if not s:
            s=Session()
        try:
            return session.query(User).filter_by(jid=jid).one()
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

class Track(object):

    @staticmethod
    def todo(session, timeout=10):
        """Get the items to do."""
        ID_QUERY="""select t.*
              from tracks t
              join user_tracks ut on (t.id = ut.track_id)
              join users u on (u.id == ut.user_id)
              where
                u.active is not null
                and u.active = :uactive
                and u.status not in ('dnd', 'offline', 'unavailable')
                and ( t.next_update < :last_update )
              order by t.last_update
          limit 60
          """
        then=datetime.datetime.now() - datetime.timedelta(minutes=timeout)
        return session.query(Track).from_statement(ID_QUERY).params(
            uactive=True, last_update=then)

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
)

_tracks_table = Table('tracks', _metadata,
    Column('id', Integer, primary_key=True, index=True, unique=True),
    Column('query', String, index=True, unique=True),
    Column('last_update', DateTime),
    Column('next_update', DateTime),
    Column('max_seen', Integer),
)

_usertrack_table = Table('user_tracks', _metadata,
    Column('id', Integer, primary_key=True, index=True),
    Column('user_id', Integer, ForeignKey('users.id')),
    Column('track_id', Integer, ForeignKey('tracks.id')),
    Column('created_at', DateTime),
)

mapper(User, _users_table, properties={
    'tracks': relation(Track, secondary=_usertrack_table, backref='tracks')
    })
mapper(UserTrack, _usertrack_table, properties={
    'user': relation(User),
    'track': relation(Track)
    })
mapper(Track, _tracks_table, properties={})
