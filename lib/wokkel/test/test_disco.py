# Copyright (c) 2003-2008 Ralph Meijer
# See LICENSE for details.

"""
Tests for L{wokkel.disco}.
"""

from twisted.internet import defer
from twisted.trial import unittest
from twisted.words.xish.xmlstream import XmlStreamFactory
from twisted.words.protocols.jabber.jid import JID
from zope.interface import implements

from wokkel.subprotocols import XMPPHandler, StreamManager

from wokkel import disco
from wokkel.test.helpers import XmlStreamStub

try:
    from twisted.words.protocols.jabber.xmlstream import toResponse
except ImportError:
    from wokkel.compat import toResponse

NS_DISCO_INFO = 'http://jabber.org/protocol/disco#info'
NS_DISCO_ITEMS = 'http://jabber.org/protocol/disco#items'

class DiscoResponder(XMPPHandler):
    implements(disco.IDisco)

    def getDiscoInfo(self, requestor, target, nodeIdentifier):
        if not nodeIdentifier:
            return defer.succeed([
                disco.DiscoIdentity('dummy', 'generic', 'Generic Dummy Entity'),
                disco.DiscoFeature('jabber:iq:version')
            ])
        else:
            return defer.succeed([])


class DiscoClientTest(unittest.TestCase):
    timeout = 2

    def setUp(self):
        self.stub = XmlStreamStub()
        self.protocol = disco.DiscoClientProtocol()
        self.protocol.xmlstream = self.stub.xmlstream
        self.protocol.connectionInitialized()

    def test_requestItems(self):
        def cb(items):
            for i,item in enumerate(items):
                pass
            self.assertEquals(1,i)

        d = self.protocol.requestItems(JID('example.org'),"foo")
        d.addCallback(cb)

        iq = self.stub.output[-1]
        self.assertEquals('example.org', iq.getAttribute('to'))
        self.assertEquals('get', iq.getAttribute('type'))
        self.assertEquals('foo', iq.query.getAttribute('node'))
        self.assertEquals(NS_DISCO_ITEMS, iq.query.uri)

        response = toResponse(iq, 'result')
        query = response.addElement((NS_DISCO_ITEMS, 'query'))

        element = query.addElement("item")
        element['jid'] = "test.example.org"
        element['node'] = "music"
        element["name"] = 'Music from the time of Shakespeare'

        element = query.addElement("item")
        element['jid'] = "test2.example.org"

        self.stub.send(response)
        return d

    def test_requestInfo(self):
        def cb(items):
            for i,item in enumerate(items):
                pass
            self.assertEquals(2,i)

        d = self.protocol.requestInfo(JID('example.org'),"foo")
        d.addCallback(cb)

        iq = self.stub.output[-1]
        self.assertEquals('example.org', iq.getAttribute('to'))
        self.assertEquals('get', iq.getAttribute('type'))
        self.assertEquals('foo', iq.query.getAttribute('node'))
        self.assertEquals(NS_DISCO_INFO, iq.query.uri)

        response = toResponse(iq, 'result')
        query = response.addElement((NS_DISCO_INFO, 'query'))

        element = query.addElement("identity")
        element['category'] = "conference" # required
        element['type'] = "text" # required
        element["name"] = 'Romeo and Juliet, Act II, Scene II' # optional

        element = query.addElement("feature")
        element['var'] = "http://jabber.org/protocol/disco#info" # required

        element = query.addElement("feature")
        element['var'] = "http://jabber.org/protocol/disco#info"

        self.stub.send(response)
        return d


class DiscoHandlerTest(unittest.TestCase):
    def test_DiscoInfo(self):
        factory = XmlStreamFactory()
        sm = StreamManager(factory)
        disco.DiscoHandler().setHandlerParent(sm)
        DiscoResponder().setHandlerParent(sm)
        xs = factory.buildProtocol(None)
        output = []
        xs.send = output.append
        xs.connectionMade()
        xs.dispatch(xs, "//event/stream/authd")
        xs.dataReceived("<stream>")
        xs.dataReceived("""<iq from='test@example.com' to='example.com'
                               type='get'>
                             <query xmlns='%s'/>
                           </iq>""" % NS_DISCO_INFO)
        reply = output[0]
        self.assertEqual(NS_DISCO_INFO, reply.query.uri)
        self.assertEqual(NS_DISCO_INFO, reply.query.identity.uri)
        self.assertEqual('dummy', reply.query.identity['category'])
        self.assertEqual('generic', reply.query.identity['type'])
        self.assertEqual('Generic Dummy Entity', reply.query.identity['name'])
        self.assertEqual(NS_DISCO_INFO, reply.query.feature.uri)
        self.assertEqual('jabber:iq:version', reply.query.feature['var'])

