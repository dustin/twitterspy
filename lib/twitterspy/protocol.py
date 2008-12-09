#!/usr/bin/env python

from twisted.internet import task
from twisted.words.xish import domish
from twisted.words.protocols.jabber.jid import JID
from wokkel.xmppim import MessageProtocol, PresenceClientProtocol
from wokkel.xmppim import AvailablePresence
from wokkel.client import XMPPHandler

import xmpp_commands
import config
import models

class TwitterspyProtocol(MessageProtocol, PresenceClientProtocol):

    def __init__(self):
        super(TwitterspyProtocol, self).__init__()
        self._tracking=-1
        self._users=-1

    def connectionInitialized(self):
        MessageProtocol.connectionInitialized(self)
        PresenceClientProtocol.connectionInitialized(self)

    def connectionMade(self):
        print "Connected!"

        self.commands=xmpp_commands.all_commands
        print "Loaded commands: ", `self.commands.keys()`

        # send initial presence
        self._tracking=-1
        self._users=-1
        self.update_presence()

    def update_presence(self):
        session=models.Session()
        try:
            tracking=session.query(models.Track).count()
            users=session.query(models.User).count()
            if tracking != self._tracking or users != self._users:
                status="Tracking %s topics for %s users" % (tracking, users)
                self.available(None, None, {None: status})
                self._tracking = tracking
                self._users = users
        finally:
            session.close()

    def connectionLost(self, reason):
        print "Disconnected!"

    def typing_notification(self, jid):
        """Send a typing notification to the given jid."""

        msg = domish.Element((None, "message"))
        msg["to"] = jid
        msg["from"] = config.SCREEN_NAME
        msg.addElement(('jabber:x:event', 'x')).addElement("composing")

        self.send(msg)

    def send_plain(self, jid, content):
        msg = domish.Element((None, "message"))
        msg["to"] = jid
        msg["from"] = config.SCREEN_NAME
        msg["type"] = 'chat'
        msg.addElement("body", content=content)

        self.send(msg)

    def get_user(self, msg, session):
        jid=JID(msg['from'])
        try:
            rv=models.User.by_jid(jid.userhost(), session)
        except:
            print "Getting user without the jid in the DB (%s)" % jid.full()
            rv=models.User.update_status(jid.userhost(), None, session)
            self.subscribe(jid)
        return rv;

    def onMessage(self, msg):
        if msg["type"] == 'chat' and hasattr(msg, "body") and msg.body:
            self.typing_notification(msg['from'])
            a=unicode(msg.body).split(' ', 1)
            args = None
            if len(a) > 1:
                args=a[1]
            if self.commands.has_key(a[0].lower()):
                session=models.Session()
                try:
                    self.commands[a[0].lower()](self.get_user(msg, session),
                        self, args, session)
                    session.commit()
                finally:
                    session.close()
            else:
                self.send_plain(msg['from'], 'No such command: ' + a[0])
            self.update_presence()

    # presence stuff
    def availableReceived(self, entity, show=None, statuses=None, priority=0):
        print "Available from %s (%s, %s)" % (entity.full(), show, statuses)
        models.User.update_status(entity.userhost(), show)

    def unavailableReceived(self, entity, statuses=None):
        print "Unavailable from %s" % entity.userhost()
        models.User.update_status(entity.userhost(), 'unavailable')

    def subscribedReceived(self, entity):
        print "Subscribe received from %s" % (entity.userhost())
        welcome_message="""Welcome to twitterspy.

Here you can use your normal IM client to post to twitter, track topics, watch
your friends, make new ones, and more.

Type "help" to get started.
"""
        self.send_plain(entity.full(), welcome_message)
        session = models.Session()
        try:
            msg = "New subscriber: %s ( %d )" % (entity.userhost(),
                session.query(models.User).count())
            for a in config.ADMINS:
                self.send_plain(a, msg)
        finally:
            session.close()

    def unsubscribedReceived(self, entity):
        print "Unsubscribed received from %s" % (entity.userhost())
        models.User.update_status(entity.userhost(), 'unsubscribed')
        self.unsubscribe(entity)
        self.unsubscribed(entity)

    def subscribeReceived(self, entity):
        print "Subscribe received from %s" % (entity.userhost())
        self.subscribe(entity)
        self.subscribed(entity)
        self.update_presence()

    def unsubscribeReceived(self, entity):
        print "Unsubscribe received from %s" % (entity.userhost())
        models.User.update_status(entity.userhost(), 'unsubscribed')
        self.unsubscribe(entity)
        self.unsubscribed(entity)
        self.update_presence()

# From https://mailman.ik.nu/pipermail/twisted-jabber/2008-October/000171.html
class KeepAlive(XMPPHandler):

    interval = 300
    lc = None

    def connectionInitialized(self):
        self.lc = task.LoopingCall(self.ping)
        self.lc.start(self.interval)

    def connectionLost(self, *args):
        if self.lc:
            self.lc.stop()

    def ping(self):
        print "Stayin' alive"
        self.send(" ")
