import sys
sys.path.insert(0,"lib/twitty-twister/lib")
sys.path.insert(0,"lib")

from twisted.application import service
from twisted.internet import task, reactor
from twisted.words.protocols.jabber import jid
from wokkel.client import XMPPClient
from wokkel.generic import VersionHandler
import twitter

from twitterspy import config
from twitterspy import protocol
from twitterspy import scheduling

# Set the user agent for twitter
twitter.Twitter.agent = "twitterspy"

application = service.Application("twitterspy")

xmppclient = XMPPClient(jid.internJID(config.SCREEN_NAME),
    config.CONF.get('xmpp', 'pass'))
xmppclient.logTraffic = False

# Stream handling protocols for twitterspy
protocols = [protocol.TwitterspyPresenceProtocol,
    protocol.TwitterspyMessageProtocol]

for p in protocols:
    handler=p()
    handler.setHandlerParent(xmppclient)

VersionHandler('twitterspy', config.VERSION).setHandlerParent(xmppclient)
protocol.KeepAlive().setHandlerParent(xmppclient)
xmppclient.setServiceParent(application)

task.LoopingCall(scheduling.tally_results).start(60)
