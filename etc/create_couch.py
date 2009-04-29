#!/usr/bin/env python

import sys
sys.path.extend(["lib", "../lib"])

from twisted.internet import reactor, defer

from twitterspy import db, cache

def parse_timestamp(ts):
    return None

@defer.deferredGenerator
def create_database():
    couch = db.get_couch()
    d = couch.createDB(db.DB_NAME)
    wfd = defer.waitForDeferred(d)
    yield wfd
    print wfd.getResult()

    doc="""
   {"language": "javascript",
   "views": {
       "counts": {
           "map": "function(doc) {
  if(doc.doctype == 'User') {
    var cnt = 0;
    if(doc.tracks) {
        cnt = doc.tracks.length;
    }
    emit(null, {users: 1, tracks: cnt});
  }
}",
           "reduce": "function(key, values) {
  var result = {users: 0, tracks: 0};
  values.forEach(function(p) {
     result.users += p.users;
     result.tracks += p.tracks;
  });
  return result;
}"
       },
       "status": {
           "map": "function(doc) {
  if(doc.doctype == 'User') {
    emit(doc.status, 1);
  }
}",
           "reduce": "function(k, v) {
  return sum(v);
}"
       },
       "service": {
           "map": "function(doc) {
  emit(doc.service_jid, 1);
}",
           "reduce": "function(k, v) {
  return sum(v);
}"
       }
   }}
"""
    d = couch.saveDoc(db.DB_NAME, doc, '_design/counts')
    wfd = defer.waitForDeferred(d)
    yield wfd
    print wfd.getResult()

    doc="""
{"language":"javascript","views":{"query_counts":{"map":"function(doc) {\n  if(doc.doctype == 'User') {\n    doc.tracks.forEach(function(query) {\n      emit(query, 1);\n    });\n  }\n}","reduce":"function(key, values) {\n   return sum(values);\n}"}}}
"""

    d = couch.saveDoc(db.DB_NAME, doc, '_design/query_counts')
    wfd = defer.waitForDeferred(d)
    yield wfd
    print wfd.getResult()

    doc="""
   {"language": "javascript",
   "views": {
       "active": {
           "map": "function(doc) {
  if(doc.doctype == 'User' && doc.active) {
    emit(null, doc._id);
  }
}"
       },
       "to_be_migrated": {
           "map": "function(doc) {
  if(doc.service_jid === 'twitterspy@jabber.org/bot') {
    emit(doc.service_jid, null);
  }
}"
       }
   }}
"""

    d = couch.saveDoc(db.DB_NAME, doc, '_design/users')
    wfd = defer.waitForDeferred(d)
    yield wfd
    print wfd.getResult()

    reactor.stop()

reactor.callWhenRunning(cache.connect)
reactor.callWhenRunning(create_database)
reactor.run()
