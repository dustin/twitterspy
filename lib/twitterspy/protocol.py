#!/usr/bin/env python

from __future__ import with_statement

import time

from twisted.python import log
from twisted.internet import protocol, reactor, threads
from twisted.words.xish import domish
from twisted.words.protocols.jabber.jid import JID
from twisted.words.protocols.jabber.xmlstream import IQ
from twisted.protocols import memcache

from wokkel.xmppim import MessageProtocol, PresenceClientProtocol
from wokkel.xmppim import AvailablePresence

import db
import xmpp_commands
import config
import scheduling
import string

current_conn = None
presence_conn = None
mc = None

class MemcacheFactory(protocol.ReconnectingClientFactory):

    def buildProtocol(self, addr):
        global mc
        self.resetDelay()
        log.msg("Connected to memcached.")
        mc = memcache.MemCacheProtocol()
        return mc

class TwitterspyMessageProtocol(MessageProtocol):

    def __init__(self):
        super(TwitterspyMessageProtocol, self).__init__()
        self._pubid = 1
        self.__connectMemcached()

        goodChars=string.letters + string.digits + "/=,_+.-~@"
        self.jidtrans = self._buildGoodSet(goodChars)

    def _buildGoodSet(self, goodChars, badChar='_'):
        allChars=string.maketrans("", "")
        badchars=string.translate(allChars, allChars, goodChars)
        rv=string.maketrans(badchars, badChar * len(badchars))
        return rv

    def connectionMade(self):
        log.msg("Connected!")

        commands=xmpp_commands.all_commands
        self.commands={}
        for c in commands.values():
            self.commands[c.name] = c
            for a in c.aliases:
                self.commands[a] = c
        log.msg("Loaded commands: %s" % `sorted(commands.keys())`)

        # Let the scheduler know we connected.
        scheduling.connected()

        self._pubid = 1

        global current_conn
        current_conn = self

    def __connectMemcached(self):
        reactor.connectTCP('localhost', memcache.DEFAULT_PORT,
            MemcacheFactory())

    def connectionLost(self, reason):
        log.msg("Disconnected!")
        global current_conn
        current_conn = None
        scheduling.disconnected()

    def _gen_id(self, prefix):
        self._pubid += 1
        return prefix + str(self._pubid)

    def publish_mood(self, mood_str, text):
        iq = IQ(self.xmlstream, 'set')
        iq['from'] = config.SCREEN_NAME
        pubsub = iq.addElement(('http://jabber.org/protocol/pubsub', 'pubsub'))
        moodpub = pubsub.addElement('publish')
        moodpub['node'] = 'http://jabber.org/protocol/mood'
        item = moodpub.addElement('item')
        mood = item.addElement(('http://jabber.org/protocol/mood', 'mood'))
        mood.addElement(mood_str)
        mood.addElement('text').addContent(text)
        def _doLog(x):
            log.msg("Delivered mood: %s (%s)" % (mood_str, text))
        d = iq.send()
        d.addErrback(log.err)
        d.addCallback(_doLog)
        log.msg("Delivering mood: %s" % iq.toXml())
        self.send(iq)

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
        msg.addRawXml(u"<body>" + unicode(body) + u"</body>")
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

    def onError(self, msg):
        log.msg("Error received for %s: %s" % (msg['from'], msg.toXml()))
        scheduling.unavailable_user(JID(msg['from']))

    def onMessage(self, msg):
        try:
            self.__onMessage(msg)
        except KeyError:
            log.err()

    def __onUserMessage(self, user, a, args, msg):
        cmd = self.commands.get(a[0].lower())
        if cmd:
            cmd(user, self, args)
        else:
            d = None
            if user.auto_post:
                d=self.commands['post']
            elif a[0][0] == '@':
                d=self.commands['post']
                if d:
                    d(user, self, unicode(msg.body).strip())
                else:
                    self.send_plain(msg['from'],
                                    "No such command: %s\n"
                                    "Send 'help' for known commands\n"
                                    "If you intended to post your message, "
                                    "please start your message with 'post', or see "
                                    "'help autopost'" % a[0])

    def __onMessage(self, msg):
        if msg["type"] == 'chat' and hasattr(msg, "body") and msg.body:
            self.typing_notification(msg['from'])
            a=unicode(msg.body).strip().split(None, 1)
            args = a[1] if len(a) > 1 else None
            db.User.by_jid(JID(msg['from']).userhost()
                           ).addCallback(self.__onUserMessage, a, args, msg)
        else:
            log.msg("Non-chat/body message: %s" % msg.toXml())

class TwitterspyPresenceProtocol(PresenceClientProtocol):

    _tracking=-1
    _users=-1

    def connectionMade(self):
        self._tracking=-1
        self._users=-1
        self.update_presence()

        global presence_conn
        presence_conn = self

    def update_presence(self):
        try:
            if scheduling.available_requests > 0:
                self._update_presence_ready()
            else:
                self._update_presence_not_ready()
        except:
            log.err()

    def _update_presence_ready(self):
        def gotResult(counts):
            users = counts['users']
            tracking = counts['tracks']
            if tracking != self._tracking or users != self._users:
                status="Tracking %s topics for %s users" % (tracking, users)
                self.available(None, None, {None: status})
                self._tracking = tracking
                self._users = users
        db.model_counts().addCallback(gotResult)

    def _update_presence_not_ready(self):
        status="Ran out of Twitter API requests."
        self.available(None, 'away', {None: status})
        self._tracking = -1
        self._users = -1

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

    def subscribedReceived(self, entity):
        log.msg("Subscribe received from %s" % (entity.userhost()))
        welcome_message="""Welcome to twitterspy.

Here you can use your normal IM client to post to twitter, track topics, watch
your friends, make new ones, and more.

Type "help" to get started.
"""
        global current_conn
        current_conn.send_plain(entity.full(), welcome_message)
        def send_noticies(counts):
            cnt = counts['users']
            msg = "New subscriber: %s ( %d )" % (entity.userhost(), cnt)
            for a in config.ADMINS:
                current_conn.send_plain(a, msg)
        db.model_counts().addCallback(send_noticies)

    def _set_status(self, u, status):
        u.status=status
        u.save()

    def _find_and_set_status(self, jid, status):
        db.User.by_jid(jid).addCallback(self._set_status, 'unsubscribed')

    def unsubscribedReceived(self, entity):
        log.msg("Unsubscribed received from %s" % (entity.userhost()))
        self._find_and_set_status(entity.userhost(), 'unsubscribed')
        self.unsubscribe(entity)
        self.unsubscribed(entity)

    def subscribeReceived(self, entity):
        log.msg("Subscribe received from %s" % (entity.userhost()))
        self.subscribe(entity)
        self.subscribed(entity)
        self.update_presence()

    def unsubscribeReceived(self, entity):
        log.msg("Unsubscribe received from %s" % (entity.userhost()))
        self._find_and_set_status(entity.userhost(), 'unsubscribed')
        self.unsubscribe(entity)
        self.unsubscribed(entity)
        self.update_presence()
