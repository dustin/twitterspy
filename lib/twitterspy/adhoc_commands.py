from zope.interface import implements

from twisted.python import log
from twisted.internet import defer
from twisted.words.xish import domish
from wokkel.subprotocols import XMPPHandler, IQHandlerMixin
from twisted.words.protocols.jabber import jid, error
from twisted.words.protocols.jabber.xmlstream import toResponse
from wokkel import disco
from wokkel import generic
from wokkel import data_form
from wokkel.iwokkel import IDisco

import db
import protocol
import scheduling

NS_CMD = 'http://jabber.org/protocol/commands'
CMD = generic.IQ_SET + '/command[@xmlns="' + NS_CMD + '"]'

all_commands = {}

def form_required(orig):
    def every(self, user, iq, cmd):
        if cmd.firstChildElement():
            form = data_form.Form.fromElement(cmd.firstChildElement())
            return orig(self, user, iq, cmd, form)
        else:
            form = data_form.Form(formType="form", title=self.name)
            self.fillForm(user, iq, cmd, form)
            return self.genFormCmdResponse(iq, cmd, form)
    return every

class BaseCommand(object):
    """Base class for xep 0050 command processors."""

    def __init__(self, node, name):
        self.node = node
        self.name = name

    def _genCmdResponse(self, iq, cmd, status=None):

        command = domish.Element(('http://jabber.org/protocol/commands',
                                     "command"))
        command['node'] = cmd['node']
        if status:
            command['status'] = status
        try:
            command['action'] = cmd['action']
        except KeyError:
            pass

        return command

    def genFormCmdResponse(self, iq, cmd, form):
        command = self._genCmdResponse(iq, cmd, 'executing')

        actions = command.addElement('actions')
        actions['execute'] = 'next'
        actions.addElement('next')

        command.addChild(form.toElement())

        return command

    def __call__(self, user, iq, cmd):
        # Will return success
        pass

class TrackManagementCommand(BaseCommand):

    def __init__(self):
        super(TrackManagementCommand, self).__init__('tracks',
                                                     'List and manage tracks')

    def fillForm(self, user, iq, cmd, form):
        form.instructions = ["Select the items you no longer wish to track."]
        form.addField(data_form.Field(var='tracks', fieldType='list-multi',
                                      options=(data_form.Option(v, v)
                                               for v in sorted(user.tracks))))

    @form_required
    def __call__(self, user, iq, cmd, form):
        vals = set(form.fields['tracks'].values)
        log.msg("Removing:  %s" % vals)
        user.tracks = list(set(user.tracks).difference(vals))

        def worked(stuff):
            for v in vals:
                scheduling.queries.untracked(user.jid, v)

        user.save().addCallback(worked)

class TrackManagementCommand(BaseCommand):

    def __init__(self):
        super(TrackManagementCommand, self).__init__('tracks',
                                                     'List and manage tracks')

    def fillForm(self, user, iq, cmd, form):
        form.instructions = ["Select the items you no longer wish to track."]
        form.addField(data_form.Field(var='tracks', fieldType='list-multi',
                                      options=(data_form.Option(v, v)
                                               for v in sorted(user.tracks))))

    @form_required
    def __call__(self, user, iq, cmd, form):
        vals = set(form.fields['tracks'].values)
        log.msg("Removing:  %s" % vals)
        user.tracks = list(set(user.tracks).difference(vals))

        def worked(stuff):
            for v in vals:
                scheduling.queries.untracked(user.jid, v)

        user.save().addCallback(worked)

for __t in (t for t in globals().values() if isinstance(type, type(t))):
    if BaseCommand in __t.__mro__:
        try:
            i = __t()
            all_commands[i.node] = i
        except TypeError, e:
            # Ignore abstract bases
            log.msg("Error loading %s: %s" % (__t.__name__, str(e)))
            pass

class AdHocHandler(XMPPHandler, IQHandlerMixin):

    implements(IDisco)

    iqHandlers = { CMD: 'onCommand' }

    def connectionInitialized(self):
        super(AdHocHandler, self).connectionInitialized()
        self.xmlstream.addObserver(CMD, self.handleRequest)

    def _onUserCmd(self, user, iq, cmd):
        return all_commands[cmd['node']](user, iq, cmd)

    def onCommand(self, iq):
        log.msg("Got an adhoc command request")
        cmd = iq.firstChildElement()
        assert cmd.name == 'command'

        return db.User.by_jid(jid.JID(iq['from']).userhost()
                              ).addCallback(self._onUserCmd, iq, cmd)

    def getDiscoInfo(self, requestor, target, node):
        info = set()

        if node:
            info.add(disco.DiscoIdentity('automation', 'command-node'))
            info.add(disco.DiscoFeature('http://jabber.org/protocol/commands'))
        else:
            info.add(disco.DiscoFeature(NS_CMD))

        return defer.succeed(info)

    def getDiscoItems(self, requestor, target, node):
        myjid = jid.internJID(protocol.default_conn.jid)
        return defer.succeed([disco.DiscoItem(myjid, c.node, c.name)
                              for c in all_commands.values()])

