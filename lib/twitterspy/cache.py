from twisted.python import log
from twisted.internet import protocol, reactor
from twisted.protocols import memcache

mc = None

class MemcacheFactory(protocol.ReconnectingClientFactory):

    def buildProtocol(self, addr):
        global mc
        self.resetDelay()
        log.msg("Connected to memcached.")
        mc = memcache.MemCacheProtocol()
        return mc

def connect():
    reactor.connectTCP('localhost', memcache.DEFAULT_PORT,
                       MemcacheFactory())
