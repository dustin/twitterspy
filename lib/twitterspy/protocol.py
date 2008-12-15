#!/usr/bin/env python

from __future__ import with_statement

from twisted.python import log
from twisted.internet import task, protocol, reactor
from twisted.words.xish import domish
from twisted.words.protocols.jabber.jid import JID
from twisted.protocols import memcache

from wokkel.xmppim import MessageProtocol, PresenceClientProtocol
from wokkel.xmppim import AvailablePresence
from wokkel.client import XMPPHandler

import xmpp_commands
import config
import models
import scheduling
import string

current_conn = None
mc = None

class MemcacheFactory(protocol.ReconnectingClientFactory):

    def buildProtocol(self, addr):
        global mc
        self.resetDelay()
        log.msg("Connected to memcached.")
        mc = memcache.MemCacheProtocol()
        return mc

class TwitterspyProtocol(MessageProtocol, PresenceClientProtocol):

    def __init__(self):
        super(TwitterspyProtocol, self).__init__()
        self._tracking=-1
        self._users=-1
        self.__connectMemcached()

        goodChars=string.letters + string.digits + "/=,_+.-~@"
        self.jidtrans = self._buildGoodSet(goodChars)

    def _buildGoodSet(self, goodChars, badChar='_'):
        allChars=string.maketrans("", "")
        badchars=string.translate(allChars, allChars, goodChars)
        rv=string.maketrans(badchars, badChar * len(badchars))
        return rv

    def connectionInitialized(self):
        MessageProtocol.connectionInitialized(self)
        PresenceClientProtocol.connectionInitialized(self)

    def connectionMade(self):
        log.msg("Connected!")

        self.commands=xmpp_commands.all_commands
        log.msg("Loaded commands: %s" % `self.commands.keys()`)

        # Let the scheduler know we connected.
        scheduling.connected()

        # send initial presence
        self._tracking=-1
        self._users=-1
        self.update_presence()

        global current_conn
        current_conn = self

    def __connectMemcached(self):
        reactor.connectTCP('localhost', memcache.DEFAULT_PORT,
            MemcacheFactory())

    @models.wants_session
    def update_presence(self, session):
        tracking=session.query(models.Track).count()
        users=session.query(models.User).count()
        if tracking != self._tracking or users != self._users:
            status="Tracking %s topics for %s users" % (tracking, users)
            self.available(None, None, {None: status})
            self._tracking = tracking
            self._users = users

    def connectionLost(self, reason):
        log.msg("Disconnected!")
        global current_conn
        current_conn = None
        scheduling.disconnected()

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

    def send_html(self, jid, body, html):
        msg = domish.Element((None, "message"))
        msg["to"] = jid
        msg["from"] = config.SCREEN_NAME
        msg["type"] = 'chat'
        html = u"<html xmlns='http://jabber.org/protocol/xhtml-im'><body xmlns='http://www.w3.org/1999/xhtml'>"+unicode(html)+u"</body></html>"
        msg.addElement("body", content=unicode(body))
        msg.addRawXml(unicode(html))

        self.send(msg)

    def send_html_deduped(self, jid, body, html, key):
        key = string.translate(str(key), self.jidtrans)[0:128]
        def checkedSend(is_new, jid, body, html):
            if is_new:
                log.msg("Sending %s" % key)
                self.send_html(jid, body, html)
            else:
                log.msg("Skipping %s" % key)
        global mc
        mc.add(key, "x").addCallback(checkedSend, jid, body, html)

    def get_user(self, msg, session):
        jid=JID(msg['from'])
        try:
            rv=models.User.by_jid(jid.userhost(), session)
        except:
            log.msg("Getting user without the jid in the DB (%s)" % jid.full())
            rv=models.User.update_status(jid.userhost(), None, session)
            self.subscribe(jid)
        return rv;

    def onError(self, msg):
        log.msg("Error received for %s: %s" % (msg['to'], msg.toXml()))
        scheduling.unavailable_user(JID(msg['from']))

    def onMessage(self, msg):
        if msg["type"] == 'chat' and hasattr(msg, "body") and msg.body:
            self.typing_notification(msg['from'])
            a=unicode(msg.body).split(' ', 1)
            args = a[1] if len(a) > 1 else None
            with models.Session() as session:
                user = self.get_user(msg, session)
                cmd = self.commands.get(a[0].lower())
                if cmd:
                    cmd(user, self, args, session)
                else:
                    d = self.commands['post'] if user.auto_post else None
                    if d:
                        d(user, self, unicode(msg.body), session)
                    else:
                        self.send_plain(msg['from'],
                            "No such command: %s\n"
                            "Send 'help' for known commands\n"
                            "If you intended to post your message, "
                            "please start your message with 'post', or see "
                            "'help autopost'" % a[0])
                session.commit()
            self.update_presence()
        else:
            log.msg("Non-chat/body message: %s" % msg.toXml())

    # presence stuff
    def availableReceived(self, entity, show=None, statuses=None, priority=0):
        log.msg("Available from %s (%s, %s, pri=%s)" % (
            entity.full(), show, statuses, priority))
        if priority >= 0 and show not in ['xa', 'dnd']:
            scheduling.available_user(entity)
        else:
            log.msg("Marking jid unavailable due to negative priority or "
                "being somewhat unavailable.")
            scheduling.unavailable_user(entity)

    def unavailableReceived(self, entity, statuses=None):
        log.msg("Unavailable from %s" % entity.full())
        scheduling.unavailable_user(entity)

    @models.wants_session
    def subscribedReceived(self, entity, session):
        log.msg("Subscribe received from %s" % (entity.userhost()))
        welcome_message="""Welcome to twitterspy.

Here you can use your normal IM client to post to twitter, track topics, watch
your friends, make new ones, and more.

Type "help" to get started.
"""
        self.send_plain(entity.full(), welcome_message)
        msg = "New subscriber: %s ( %d )" % (entity.userhost(),
            session.query(models.User).count())
        for a in config.ADMINS:
            self.send_plain(a, msg)

    def unsubscribedReceived(self, entity):
        log.msg("Unsubscribed received from %s" % (entity.userhost()))
        models.User.update_status(entity.userhost(), 'unsubscribed')
        self.unsubscribe(entity)
        self.unsubscribed(entity)

    def subscribeReceived(self, entity):
        log.msg("Subscribe received from %s" % (entity.userhost()))
        self.subscribe(entity)
        self.subscribed(entity)
        self.update_presence()

    def unsubscribeReceived(self, entity):
        log.msg("Unsubscribe received from %s" % (entity.userhost()))
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
        log.msg("Stayin' alive")
        self.send(" ")
