# -*- test-case-name: test_paisley -*-
# Copyright (c) 2007-2008
# See LICENSE for details.

"""
CouchDB client.
"""

import simplejson
from urllib import urlencode

from twisted.web.client import HTTPClientFactory

try:
    from base64 import b64encode
except ImportError:
    import base64

    def b64encode(s):
        return "".join(base64.encodestring(s).split("\n"))


try:
    from functools import partial
except ImportError:
    class partial(object):
        def __init__(self, fn, *args, **kw):
            self.fn = fn
            self.args = args
            self.kw = kw

        def __call__(self, *args, **kw):
            if kw and self.kw:
                d = self.kw.copy()
                d.update(kw)
            else:
                d = kw or self.kw
            return self.fn(*(self.args + args), **d)



class CouchDB(object):
    """
    CouchDB client: hold methods for accessing a couchDB.
    """

    def __init__(self, host, port=5984, dbName=None):
        """
        Initialize the client for given host.

        @param host: address of the server.
        @type host: C{str}

        @param port: if specified, the port of the server.
        @type port: C{int}

        @param dbName: if specified, all calls needing a database name will use
            this one by default.
        @type dbName: C{str}
        """
        self.host = host
        self.port = int(port)
        self.url_template = "http://%s:%s%%s" % (self.host, self.port)
        if dbName is not None:
            self.bindToDB(dbName)


    def parseResult(self, result):
        """
        Parse JSON result from the DB.
        """
        return simplejson.loads(result)


    def bindToDB(self, dbName):
        """
        Bind all operations asking for a DB name to the given DB.
        """
        for methname in ["createDB", "deleteDB", "infoDB", "listDoc",
                         "openDoc", "saveDoc", "deleteDoc", "openView",
                         "tempView"]:
            method = getattr(self, methname)
            newMethod = partial(method, dbName)
            setattr(self, methname, newMethod)


    # Database operations

    def createDB(self, dbName):
        """
        Creates a new database on the server.
        """
        # Responses: {u'ok': True}, 409 Conflict, 500 Internal Server Error
        return self.put("/%s/" % (dbName,), ""
            ).addCallback(self.parseResult)


    def deleteDB(self, dbName):
        """
        Deletes the database on the server.
        """
        # Responses: {u'ok': True}, 404 Object Not Found
        return self.delete("/%s/" % (dbName,)
            ).addCallback(self.parseResult)


    def listDB(self):
        """
        List the databases on the server.
        """
        # Responses: list of db names
        return self.get("/_all_dbs").addCallback(self.parseResult)


    def infoDB(self, dbName):
        """
        Returns info about the couchDB.
        """
        # Responses: {u'update_seq': 0, u'db_name': u'mydb', u'doc_count': 0}
        # 404 Object Not Found
        return self.get("/%s/" % (dbName,)
            ).addCallback(self.parseResult)


    # Document operations

    def listDoc(self, dbName, reverse=False, startKey=0, count=-1):
        """
        List all documents in a given database.
        """
        # Responses: {u'rows': [{u'_rev': -1825937535, u'_id': u'mydoc'}],
        # u'view': u'_all_docs'}, 404 Object Not Found
        uri = "/%s/_all_docs" % (dbName,)
        args = {}
        if reverse:
            args["reverse"] = "true"
        if startKey > 0:
            args["startkey"] = int(startKey)
        if count >= 0:
            args["count"] = int(count)
        if args:
            uri += "?%s" % (urlencode(args),)
        return self.get(uri
            ).addCallback(self.parseResult)


    def openDoc(self, dbName, docId, revision=None, full=False, attachment=""):
        """
        Open a document in a given database.

        @param revision: if specified, the revision of the document desired.
        @type revision: C{str}

        @param full: if specified, return the list of all the revisions of the
            document, along with the document itself.
        @type full: C{bool}

        @param attachment: if specified, return the named attachment from the
            document.
        @type attachment: C{str}
        """
        # Responses: {u'_rev': -1825937535, u'_id': u'mydoc', ...}
        # 404 Object Not Found
        uri = "/%s/%s" % (dbName, docId)
        if revision is not None:
            uri += "?%s" % (urlencode({"rev": revision}),)
        elif full:
            uri += "?%s" % (urlencode({"full": "true"}),)
        elif attachment:
            uri += "?%s" % (urlencode({"attachment": attachment}),)
            # No parsing
            return  self.get(uri)
        return self.get(uri
            ).addCallback(self.parseResult)


    def addAttachments(self, document, attachments):
        """
        Add attachments to a document, before sending it to the DB.

        @param document: the document to modify.
        @type document: C{dict}

        @param attachments: the attachments to add.
        @type attachments: C{dict}
        """
        document.setdefault("_attachments", {})
        for name, data in attachments.iteritems():
            data = b64encode(data)
            document["_attachments"][name] = {"type": "base64", "data": data}


    def saveDoc(self, dbName, body, docId=None):
        """
        Save/create a document to/in a given database.

        @param dbName: identifier of the database.
        @type dbName: C{str}

        @param body: content of the document.
        @type body: C{str} or any structured object

        @param docId: if specified, the identifier to be used in the database.
        @type docId: C{str}
        """
        # Responses: {u'_rev': 1175338395, u'_id': u'mydoc', u'ok': True}
        # 409 Conflict, 500 Internal Server Error
        if not isinstance(body, (str, unicode)):
            body = simplejson.dumps(body)
        if docId is not None:
            d = self.put("/%s/%s" % (dbName, docId), body)
        else:
            d = self.post("/%s/" % (dbName,), body)
        return d.addCallback(self.parseResult)


    def deleteDoc(self, dbName, docId, revision):
        """
        Delete a document on given database.
        """
        # Responses: {u'_rev': 1469561101, u'ok': True}
        # 500 Internal Server Error
        return self.delete("/%s/%s?%s" % (
                dbName,
                docId,
                urlencode({'rev': revision}))
            ).addCallback(self.parseResult)


    # View operations

    def openView(self, dbName, docId, viewId, **kwargs):
        """
        Open a view of a document in a given database.
        """
        uri = "/%s/_view/%s/%s" % (dbName, docId, viewId)

        if kwargs:
            uri += "?%s" % (urlencode(kwargs),)

        return self.get(uri
            ).addCallback(self.parseResult)


    def addViews(self, document, views):
        """
        Add views to a document.

        @param document: the document to modify.
        @type document: C{dict}

        @param views: the views to add.
        @type views: C{dict}
        """
        document.setdefault("views", {})
        for name, data in views.iteritems():
            document["views"][name] = data


    def tempView(self, dbName, view):
        """
        Make a temporary view on the server.
        """
        d = self.post("/%s/_temp_view" % (dbName,), view)
        return d.addCallback(self.parseResult)


    # Basic http methods

    def _getPage(self, uri, **kwargs):
        """
        C{getPage}-like.
        """
        url = self.url_template % (uri,)
        kwargs["headers"] = {"Accept": "application/json"}
        factory = HTTPClientFactory(url, **kwargs)
        from twisted.internet import reactor
        reactor.connectTCP(self.host, self.port, factory)
        return factory.deferred


    def get(self, uri):
        """
        Execute a C{GET} at C{uri}.
        """
        return self._getPage(uri, method="GET")


    def post(self, uri, body):
        """
        Execute a C{POST} of C{body} at C{uri}.
        """
        return self._getPage(uri, method="POST", postdata=body)


    def put(self, uri, body):
        """
        Execute a C{PUT} of C{body} at C{uri}.
        """
        return self._getPage(uri, method="PUT", postdata=body)


    def delete(self, uri):
        """
        Execute a C{DELETE} at C{uri}.
        """
        return self._getPage(uri, method="DELETE")
