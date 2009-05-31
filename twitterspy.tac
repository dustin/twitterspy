import sys
sys.path.insert(0, "lib/twitty-twister/lib")
sys.path.insert(0, "lib/wokkel")
sys.path.insert(0, 'lib/twisted-longurl/lib')
sys.path.insert(0, "lib")

import ConfigParser

from twisted.application import service
from twisted.internet import task, reactor
from twisted.words.protocols.jabber import jid
from twisted.web import client
from wokkel.client import XMPPClient
from wokkel.generic import VersionHandler
from wokkel.keepalive import KeepAlive
from wokkel.disco import DiscoHandler
import twitter

from twitterspy import db
from twitterspy import cache
from twitterspy import config
from twitterspy import protocol
from twitterspy import xmpp_ping
from twitterspy import scheduling
from twitterspy import moodiness
from twitterspy import url_expansion
from twitterspy import adhoc_commands

# Set the user agent for twitter
twitter.Twitter.agent = "twitterspy"

client.HTTPClientFactory.noisy = False

application = service.Application("twitterspy")

def build_client(section):
    host = None
    try:
        host = config.CONF.get(section, 'host')
    except ConfigParser.NoSectionError:
        pass

    j = jid.internJID(config.CONF.get(section, 'jid'))

    xmppclient = XMPPClient(j, config.CONF.get(section, 'pass'), host)

    xmppclient.logTraffic = False

    # Stream handling protocols for twitterspy
    protocols = [protocol.TwitterspyPresenceProtocol,
                 protocol.TwitterspyMessageProtocol]

    for p in protocols:
        handler=p(j)
        handler.setHandlerParent(xmppclient)

    DiscoHandler().setHandlerParent(xmppclient)
    VersionHandler('twitterspy', config.VERSION).setHandlerParent(xmppclient)
    xmpp_ping.PingHandler().setHandlerParent(xmppclient)
    adhoc_commands.AdHocHandler().setHandlerParent(xmppclient)
    KeepAlive().setHandlerParent(xmppclient)
    xmppclient.setServiceParent(application)

    return xmppclient


cache.connect()
db.initialize()

build_client('xmpp')
try:
    build_client('xmpp_secondary')
except ConfigParser.NoSectionError:
    pass

task.LoopingCall(moodiness.moodiness).start(60, now=False)
task.LoopingCall(scheduling.resetRequests).start(scheduling.REQUEST_PERIOD,
                                                 now=False)

# If the expansion services are loaded, expansion will take effect
if (config.CONF.has_option('general', 'expand')
    and config.CONF.getboolean('general', 'expand')):

    # Load the url expansion services now, and refresh it every seven days.
    task.LoopingCall(url_expansion.expander.loadServices).start(86400 * 7)

