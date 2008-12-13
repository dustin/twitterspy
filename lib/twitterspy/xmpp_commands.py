import re
import sys
import time
import types
import base64
import datetime
import urlparse
import sre_constants

from twisted.words.xish import domish
from twisted.web import client
from twisted.internet import reactor
from sqlalchemy.orm import exc

import models

import twitter
import scheduling

all_commands={}

class CountingFile(object):
    """A file-like object that just counts what's written to it."""
    def __init__(self):
        self.written=0
    def write(self, b):
        self.written += len(b)
    def close(self):
        pass
    def open(self):
        pass
    def read(self):
        return None

class BaseCommand(object):
    """Base class for command processors."""

    def __get_extended_help(self):
        if self.__extended_help:
            return self.__extended_help
        else:
            return self.help

    def __set_extended_help(self, v):
        self.__extended_help=v

    extended_help=property(__get_extended_help, __set_extended_help)

    def __init__(self, name, help=None, extended_help=None):
        self.name=name
        self.help=help
        self.extended_help=extended_help

    def __call__(self, user, prot, args, session):
        raise NotImplementedError()

    def is_a_url(self, u):
        try:
            parsed = urlparse.urlparse(str(u))
            return parsed.scheme in ['http', 'https'] and parsed.netloc
        except:
            return False

class ArgRequired(BaseCommand):

    def __call__(self, user, prot, args, session):
        if self.has_valid_args(args):
            self.process(user, prot, args, session)
        else:
            prot.send_plain(user.jid, "Arguments required for %s:\n%s"
                % (self.name, self.extended_help))

    def has_valid_args(self, args):
        return args

    def process(self, user, prot, args, session):
        raise NotImplementedError()

class StatusCommand(BaseCommand):

    def __init__(self):
        super(StatusCommand, self).__init__('status', 'Check your status.')

    def __call__(self, user, prot, args, session):
        rv=[]
        rv.append("Jid:  %s" % user.jid)
        rv.append("Twitterspy status:  %s"
            % {True: 'Active', False: 'Inactive'}[user.active])
        rv.append("You are currently tracking %d topics." % len(user.tracks))
        if user.has_credentials():
            rv.append("You're logged in to twitter as %s" % (user.username))
        if user.friend_timeline_id is not None:
            rv.append("Friend tracking is enabled.")
        prot.send_plain(user.jid, "\n".join(rv))

class HelpCommand(BaseCommand):

    def __init__(self):
        super(HelpCommand, self).__init__('help', 'You need help.')

    def __call__(self, user, prot, args, session):
        rv=[]
        if args:
            c=all_commands.get(args.strip().lower(), None)
            if c:
                rv.append("Help for %s:\n" % c.name)
                rv.append(c.extended_help)
            else:
                rv.append("Unknown command %s." % args)
        else:
            for k in sorted(all_commands.keys()):
                rv.append('%s\t%s' % (k, all_commands[k].help))
        prot.send_plain(user.jid, "\n".join(rv))

class OnCommand(BaseCommand):
    def __init__(self):
        super(OnCommand, self).__init__('on', 'Enable tracks.')

    def __call__(self, user, prot, args, session):
        user.active=True
        scheduling.enable_user(user.jid)
        prot.send_plain(user.jid, "Enabled tracks.")

class OffCommand(BaseCommand):
    def __init__(self):
        super(OffCommand, self).__init__('off', 'Disable tracks.')

    def __call__(self, user, prot, args, session):
        user.active=False
        scheduling.disable_user(user.jid)
        prot.send_plain(user.jid, "Disabled tracks.")

class SearchCommand(ArgRequired):

    def __init__(self):
        super(SearchCommand, self).__init__('search',
            'Perform a search query (but do not track).')

    def process(self, user, prot, args, session):
        rv = []
        def gotResult(entry):
            rv.append(entry.author.name.split()[0] + ": " + entry.title)
        jid = user.jid
        twitter.Twitter().search(args, gotResult, {'rpp': '3'}).addCallback(
            lambda x: prot.send_plain(jid, "Results\n\n"
                + "\n\n".join(rv))).addErrback(
            lambda x: prot.send_plain(jid, "Problem performing search"))

class TWLoginCommand(ArgRequired):

    def __init__(self):
        super(TWLoginCommand, self).__init__('twlogin',
            'Set your twitter username and password (use at your own risk)')

    def process(self, user, prot, args, session):
        args = args.replace(">", "").replace("<", "")
        username, password=args.split(' ', 1)
        jid = user.jid
        twitter.Twitter(username, password).verify_credentials().addCallback(
            self.__credsVerified, prot, jid, username, password).addErrback(
            self.__credsRefused, prot, jid)

    def __credsRefused(self, e, prot, jid):
        print "Failed to verify creds for %s: %s" % (jid, e)
        prot.send_plain(jid,
            ":( Your credentials were refused. "
                "Please try again: twlogin username password")

    def __credsVerified(self, x, prot, jid, username, password):
        session = models.Session()
        try:
            user = models.User.by_jid(jid, session)
            user.username = username
            user.password = base64.encodestring(password)
            session.commit()
            prot.send_plain(user.jid, "Added credentials for %s"
                % user.username)
            scheduling.users.set_creds(jid, username, password)
        finally:
            session.close()

class TWLogoutCommand(BaseCommand):

    def __init__(self):
        super(TWLogoutCommand, self).__init__('twlogout',
            "Discard your twitter credentials.")

    def __call__(self, user, prot, args, session):
        user.username = None
        user.password = None
        prot.send_plain(user.jid, "You have been logged out.")
        scheduling.users.set_creds(user.jid, None, None)

class TrackCommand(ArgRequired):

    def __init__(self):
        super(TrackCommand, self).__init__('track', "Start tracking a topic.")

    def process(self, user, prot, args, session):
        user.track(args, session)
        if user.active:
            scheduling.queries.add(user.jid, args, 0)
            rv = "Tracking %s" % args
        else:
            rv = "Will track %s as soon as you activate again." % args
        prot.send_plain(user.jid, rv)

class UnTrackCommand(ArgRequired):

    def __init__(self):
        super(UnTrackCommand, self).__init__('untrack',
            "Stop tracking a topic.")

    def process(self, user, prot, args, session):
        if user.untrack(args, session):
            scheduling.queries.untracked(user.jid, args)
            prot.send_plain(user.jid, "Stopped tracking %s" % args)
        else:
            prot.send_plain(user.jid,
                "Didn't tracking %s (sure you were tracking it?)" % args)

class TracksCommand(BaseCommand):

    def __init__(self):
        super(TracksCommand, self).__init__('tracks',
            "List the topics you're tracking.")

    def __call__(self, user, prot, args, session):
        rv = ["Currently tracking:\n"]
        rv.extend(sorted([t.query for t in user.tracks]))
        prot.send_plain(user.jid, "\n".join(rv))

class PostCommand(ArgRequired):

    def __init__(self):
        super(PostCommand, self).__init__('post',
            "Post a message to twitter.")

    def _posted(self, id, jid, username, prot):
        url = "http://twitter.com/%s/statuses/%s" % (username, id)
        prot.send_plain(jid, ":) Your message has been posted: %s" % url)

    def _failed(self, e, jid, prot):
        print "Error updating for %s:  %s" % (jid, str(e))
        prot.send_plain(jid, ":( Failed to post your message. "
            "Your password may be wrong, or twitter may be broken.")

    def process(self, user, prot, args, session):
        if user.has_credentials():
            jid = user.jid
            twitter.Twitter(user.username, user.decoded_password()).update(
                args, 'twitterspy'
                ).addCallback(self._posted, jid, user.username, prot
                ).addErrback(self._failed, jid, prot)
        else:
            prot.send_plain(user.jid, "You must twlogin before you can post.")

class OnOffCommand(ArgRequired):

    def has_valid_args(self, args):
        return args and args.lower() in ["on", "off"]

class AutopostCommand(OnOffCommand):

    def __init__(self):
        super(AutopostCommand, self).__init__('autopost',
            "Enable or disable autopost.")

    def process(self, user, prot, args, session):
        user.auto_post = (args.lower() == "on")
        prot.send_plain(user.jid, "Autoposting is now %s." % (args.lower()))

class WatchFriendsCommand(OnOffCommand):

    def __init__(self):
        super(WatchFriendsCommand, self).__init__('watch_friends',
            "Enable or disable watching friends.")

    def _gotFriendStatus(self, jid):
        def f(entry):
            session = models.Session()
            try:
                user = models.User.by_jid(jid, session)
                user.friend_timeline_id = entry.id
            finally:
                session.close()
        return f

    def process(self, user, prot, args, session):
        if not user.has_credentials():
            prot.send_plain(user.jid,
                "You must twlogin before you can watch friends.")
            return

        args = args.lower()
        if args == 'on':
            twitter.Twitter(user.username, user.decoded_password()).friends(
                self._gotFriendStatus(user.jid), params={'count': 1})
        elif args == 'off':
            user.friend_timeline_id = None
            prot.send_plain(user.jid, "No longer watching your friends.")
        else:
            prot.send_plain(user.jid, "Watch must be 'on' or 'off'.")

for __t in (t for t in globals().values() if isinstance(type, type(t))):
    if BaseCommand in __t.__mro__:
        try:
            i = __t()
            all_commands[i.name] = i
        except TypeError, e:
            # Ignore abstract bases
            print "Error loading %s: %s" % (__t.__name__, str(e))
            pass
