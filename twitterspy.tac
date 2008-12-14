import sys
sys.path.append("lib")
sys.path.append("lib/twitty-twister/lib")

from twisted.application import service
from twisted.internet import task, reactor
from twisted.words.protocols.jabber import jid
from wokkel.client import XMPPClient
from wokkel.generic import VersionHandler

from twitterspy import config
from twitterspy import protocol

application = service.Application("twitterspy")

xmppclient = XMPPClient(jid.internJID(config.SCREEN_NAME),
    config.CONF.get('xmpp', 'pass'))
xmppclient.logTraffic = False
twitterspy=protocol.TwitterspyProtocol()
twitterspy.setHandlerParent(xmppclient)
VersionHandler('twitterspy', config.VERSION).setHandlerParent(xmppclient)
protocol.KeepAlive().setHandlerParent(xmppclient)
xmppclient.setServiceParent(application)
