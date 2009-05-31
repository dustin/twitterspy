from zope.interface import implements

from twisted.python import log
from twisted.internet import defer
from wokkel.subprotocols import XMPPHandler, IQHandlerMixin
from wokkel import disco
from wokkel import generic
from wokkel.iwokkel import IDisco

NS_PING = 'urn:xmpp:ping'
PING = generic.IQ_GET + '/ping[@xmlns="' + NS_PING + '"]'

class PingHandler(XMPPHandler, IQHandlerMixin):
    """
    XMPP subprotocol handler for Ping.

    This protocol is described in
    U{XEP-0199<http://www.xmpp.org/extensions/xep-0199.html>}.
    """

    implements(IDisco)

    iqHandlers = {PING: 'onPing'}

    def connectionInitialized(self):
        super(PingHandler, self).connectionInitialized()
        self.xmlstream.addObserver(PING, self.handleRequest)

    def onPing(self, iq):
        log.msg("Got ping from %s" % iq.getAttribute("from"))

    def getDiscoInfo(self, requestor, target, node):
        info = set()

        if not node:
            info.add(disco.DiscoFeature(NS_PING))

        return defer.succeed(info)

    def getDiscoItems(self, requestor, target, node):
        return defer.succeed([])

