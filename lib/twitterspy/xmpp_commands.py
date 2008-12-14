import re
import sys
import time
import types
import base64
import datetime
import urlparse
import sre_constants

from twisted.python import log
from twisted.words.xish import domish
from twisted.web import client
from twisted.internet import reactor
from sqlalchemy.orm import exc

import models

import twitter
import scheduling

all_commands={}

def arg_required(validator=lambda n: n):
    def f(orig):
        def every(self, user, prot, args, session):
            if validator(args):
                orig(self, user, prot, args, session)
            else:
                prot.send_plain(user.jid, "Arguments required for %s:\n%s"
                    % (self.name, self.extended_help))
        return every
    return f

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

class StatusCommand(BaseCommand):

    def __init__(self):
        super(StatusCommand, self).__init__('status', 'Check your status.')

    def __call__(self, user, prot, args, session):
        rv=[]
        rv.append("Jid:  %s" % user.jid)
        rv.append("Twitterspy status:  %s"
            % {True: 'Active', False: 'Inactive'}[user.active])
        rv.append("You are currently tracking %d topics." % len(user.tracks))
        if user.has_credentials:
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

class SearchCommand(BaseCommand):

    def __init__(self):
        super(SearchCommand, self).__init__('search',
            'Perform a search query (but do not track).')

    @arg_required()
    def __call__(self, user, prot, args, session):
        rv = []
        def gotResult(entry):
            rv.append(entry.author.name.split()[0] + ": " + entry.title)
        jid = user.jid
        twitter.Twitter().search(args, gotResult, {'rpp': '3'}).addCallback(
            lambda x: prot.send_plain(jid, "Results\n\n"
                + "\n\n".join(rv))).addErrback(
            lambda x: prot.send_plain(jid, "Problem performing search"))

class TWLoginCommand(BaseCommand):

    def __init__(self):
        super(TWLoginCommand, self).__init__('twlogin',
            'Set your twitter username and password (use at your own risk)')

    @arg_required()
    def __call__(self, user, prot, args, session):
        args = args.replace(">", "").replace("<", "")
        username, password=args.split(' ', 1)
        jid = user.jid
        twitter.Twitter(username, password).verify_credentials().addCallback(
            self.__credsVerified, prot, jid, username, password).addErrback(
            self.__credsRefused, prot, jid)

    def __credsRefused(self, e, prot, jid):
        log.msg("Failed to verify creds for %s: %s" % (jid, e))
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

class TrackCommand(BaseCommand):

    def __init__(self):
        super(TrackCommand, self).__init__('track', "Start tracking a topic.")

    @arg_required()
    def __call__(self, user, prot, args, session):
        user.track(args, session)
        if user.active:
            scheduling.queries.add(user.jid, args, 0)
            rv = "Tracking %s" % args
        else:
            rv = "Will track %s as soon as you activate again." % args
        prot.send_plain(user.jid, rv)

class UnTrackCommand(BaseCommand):

    def __init__(self):
        super(UnTrackCommand, self).__init__('untrack',
            "Stop tracking a topic.")

    @arg_required()
    def __call__(self, user, prot, args, session):
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

class PostCommand(BaseCommand):

    def __init__(self):
        super(PostCommand, self).__init__('post',
            "Post a message to twitter.")

    def _posted(self, id, jid, username, prot):
        url = "http://twitter.com/%s/statuses/%s" % (username, id)
        prot.send_plain(jid, ":) Your message has been posted: %s" % url)

    def _failed(self, e, jid, prot):
        log.msg("Error updating for %s:  %s" % (jid, str(e)))
        prot.send_plain(jid, ":( Failed to post your message. "
            "Your password may be wrong, or twitter may be broken.")

    @arg_required()
    def __call__(self, user, prot, args, session):
        if user.has_credentials:
            jid = user.jid
            twitter.Twitter(user.username, user.decoded_password).update(
                args, 'twitterspy'
                ).addCallback(self._posted, jid, user.username, prot
                ).addErrback(self._failed, jid, prot)
        else:
            prot.send_plain(user.jid, "You must twlogin before you can post.")

class FollowCommand(BaseCommand):

    def __init__(self):
        super(FollowCommand, self).__init__('follow',
            "Begin following a user.")

    def _following(self, e, jid, prot, user):
        prot.send_plain(jid, ":) Now following %s" % user)

    def _failed(self, e, jid, prot, user):
        log.msg("Failed a follow request %s" % repr(e))
        prot.send_plain(jid, ":( Failed to follow %s" % user)

    @arg_required()
    def __call__(self, user, prot, args, session):
        if user.has_credentials:
            twitter.Twitter(user.username, user.decoded_password).follow(
                str(args)).addCallback(self._following, user.jid, prot, args
                ).addErrback(self._failed, user.jid, prot, args)
        else:
            prot.send_plain(jid, "You must twlogin before you can follow.")

class LeaveUser(BaseCommand):

    def __init__(self):
        super(LeaveUser, self).__init__('leave',
            "Stop following a user.")

    def _left(self, e, jid, prot, user):
        prot.send_plain(jid, ":) No longer following %s" % user)

    def _failed(self, e, jid, prot, user):
        log.msg("Failed an unfollow request: %s", repr(e))
        prot.send_plain(jid, ":( Failed to follow %s" % user)
        prot.send_plain(jid, ":( Failed to stop following %s" % user)

    @arg_required()
    def __call__(self, user, prot, args, session):
        if user.has_credentials:
            twitter.Twitter(user.username, user.decoded_password).leave(
                str(args)).addCallback(self._left, user.jid, prot, args
                ).addErrback(self._failed, user.jid, prot, args)
        else:
            prot.send_plain(jid,
                "You must twlogin before you can stop following.")

def must_be_on_or_off(args):
    return args and args.lower() in ["on", "off"]

class AutopostCommand(BaseCommand):

    def __init__(self):
        super(AutopostCommand, self).__init__('autopost',
            "Enable or disable autopost.")

    @arg_required(must_be_on_or_off)
    def __call__(self, user, prot, args, session):
        user.auto_post = (args.lower() == "on")
        prot.send_plain(user.jid, "Autoposting is now %s." % (args.lower()))

class WatchFriendsCommand(BaseCommand):

    def __init__(self):
        super(WatchFriendsCommand, self).__init__('watch_friends',
            "Enable or disable watching friends.")

    def _gotFriendStatus(self, jid, prot):
        def f(entry):
            session = models.Session()
            try:
                user = models.User.by_jid(jid, session)
                user.friend_timeline_id = entry.id
            finally:
                session.close()
            prot.send_plain(jid, ":) Starting to watch friends.")
        return f

    @arg_required(must_be_on_or_off)
    def __call__(self, user, prot, args, session):
        if not user.has_credentials:
            prot.send_plain(user.jid,
                "You must twlogin before you can watch friends.")
            return

        args = args.lower()
        if args == 'on':
            twitter.Twitter(user.username, user.decoded_password).friends(
                self._gotFriendStatus(user.jid, prot), params={'count': '1'})
        elif args == 'off':
            user.friend_timeline_id = None
            prot.send_plain(user.jid, ":) No longer watching your friends.")
        else:
            prot.send_plain(user.jid, "Watch must be 'on' or 'off'.")

class WhoisCommand(BaseCommand):

    def __init__(self):
        super(WhoisCommand, self).__init__('whois',
            'Find out who a user is.')

    def _fail(self, e, prot, jid, u):
        prot.send_plain(user.jid, "Couldn't get info for %s" % u)

    def _gotUser(self, u, prot, jid):
        html="""Whois <a
  href="http://twitter.com/%(screen_name)s">%(screen_name)s</a><br/><br/>
Name:  %(name)s<br/>
Home:  %(url)s<br/>
Where: %(location)s<br/>
Friends: <a
  href="http://twitter.com/%(screen_name)s/friends">%(friends_count)s</a><br/>
Followers: <a
  href="http://twitter.com/%(screen_name)s/followers">%(followers_count)s</a><br/>
Recently:<br/>
        %(status_text)s
"""
        params = dict(u.__dict__)
        params['status_text'] = u.status.text
        prot.send_html(jid, "(no plain text yet)", html % params)

    @arg_required()
    def __call__(self, user, prot, args, session):
        if user.has_credentials:
            twitter.Twitter(user.username, user.decoded_password).show_user(
                str(args)).addErrback(self._fail, prot, user.jid, args
                ).addCallback(self._gotUser, prot, user.jid)
        else:
            prot.send_plain(user.jid, "You must twlogin before doing a whois.")

for __t in (t for t in globals().values() if isinstance(type, type(t))):
    if BaseCommand in __t.__mro__:
        try:
            i = __t()
            all_commands[i.name] = i
        except TypeError, e:
            # Ignore abstract bases
            log.msg("Error loading %s: %s" % (__t.__name__, str(e)))
            pass
