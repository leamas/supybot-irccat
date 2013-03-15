###
# Copyright (c) 2013, Alec Leamas
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#   * Redistributions of source code must retain the above copyright notice,
#     this list of conditions, and the following disclaimer.
#   * Redistributions in binary form must reproduce the above copyright notice,
#     this list of conditions, and the following disclaimer in the
#     documentation and/or other materials provided with the distribution.
#   * Neither the name of the author of this software nor the name of
#     contributors to this software may be used to endorse or promote products
#     derived from this software without specific prior written consent.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

# https://chris-lamb.co.uk/posts/irccat-plugin-supybot
# http://www.jibble.org/pircbot.php

''' Main plugin module. See README for usage and configuration. '''

import pickle
import time

from twisted.internet import reactor, protocol
from twisted.protocols import basic

from supybot import callbacks
from supybot import ircmsgs
from supybot import log
from supybot.commands import commalist
from supybot.commands import threading
from supybot.commands import wrap

import config

_HELP_URL = "https://github.com/leamas/supybot-irccat"


class _Section(object):
    ''' Section representation in _data. '''

    def __init__(self, password, channels):
        self.password = password
        self.channels = channels


class _Blacklist(object):
    ''' Handles blacklisting of aggressive clients. '''

    FailMax = 4   # Max # of times
    BlockTime = 20  # Time we wait in blacklisted state (seconds).

    def __init__(self):
        self._state = {}
        self.log = log.getPluginLogger('irccat.blacklist')

    def register(self, host, status):
        ''' Register an event coming from host (address) being OK/Fail. '''
        if not host in self._state:
            self._state[host] = (1, status, time.time())
            return
        count, oldstate, when = self._state[host]
        if oldstate == status:
            self._state[host] = (count + 1, oldstate, when)
            if not status and count + 1 == self.FailMax:
                self.log.warning("Blacklisting: " + host)
        else:
            self._state[host] = (1, status, time.time())

    def onList(self, host):
        ''' Return True if host is blacklisted i. e., should be blocked.'''
        if not host in self._state:
            return False
        count, oldstate, when = self._state[host]
        if oldstate:
            return False
        if count >= self.FailMax:
            if time.time() - when < self.BlockTime:
                return True
            else:
                self._state[host] = (1, oldstate, time.time())
        return False


class _Config(object):
    ''' Persistent stored, critical zone section data. '''

    def __init__(self):
        self.log = log.getPluginLogger('irccat.config')
        self._lock = threading.Lock()
        self._path = config.global_option('sectionspath').value
        self.port = config.global_option('port').value
        try:
            self._data = pickle.load(open(self._path))
        except IOError:
            self._data = {}
            self.log.warning("Can't find stored config, creating empty.")
            self._dump()
        except Exception:   # Unpickle throws just anything.
            self._data = {}
            self.log.warning("Bad stored config, creating empty.")
            self._dump()

    def _dump(self):
        ''' Update persistent data.'''
        pickle.dump(self._data, open(self._path, 'w'))

    def get(self, section_name):
        ''' Return (password, channels) tuple or raise KeyError. '''
        with self._lock:
            s = self._data[section_name]
        return s.password, s.channels

    def update(self, section_name, password, channels):
        ''' Store section data for name, creating it if required. '''
        with self._lock:
            self._data[section_name] = _Section(password, channels)
            self._dump()

    def remove(self, section_name):
        ''' Remove existing section or raise KeyError. '''
        with self._lock:
            del(self._data[section_name])
            self._dump()

    def keys(self):
        ''' Return list of section names. '''
        with self._lock:
            return list(self._data.keys())


class IrccatProtocol(basic.LineOnlyReceiver):
    ''' Line protocol: parse line, forward to channel(s). '''

    delimiter = '\n'

    def __init__(self, irc, config_, blacklist):
        self.irc = irc
        self.config = config_
        self.blacklist = blacklist
        self.log = log.getPluginLogger('irccat.protocol')
        self.peer = None

    def connectionMade(self):
        # if blacklisted: self.transport.abortConnection()
        self.peer = self.transport.getPeer()
        if self.blacklist.onList(self.peer.host):
            self.transport.abortConnection()

    def connectionLost(self, reason):            # pylint: disable=W0222
        self.peer = None

    def lineReceived(self, text):
        ''' Handle one line of input from client. '''

        def warning(what):
            ''' Log  a warning about bad input. '''
            if self.peer:
                what += ' from: ' + str(self.peer.host)
            self.log.warning(what)
            self.blacklist.register(self.peer.host, False)

        try:
            section, pw, data = text.split(';', 2)
        except ValueError:
            warning('Illegal format: ' + text)
            return
        try:
            my_pw, channels = self.config.get(section)
        except KeyError:
            warning("No such section: " + section)
            return
        if my_pw != pw:
            warning('Bad password: ' + pw)
            return
        if not channels:
            warning('Empty channel list: ' + section)
        for channel in channels:
            self.irc.queueMsg(ircmsgs.notice(channel, data))
        self.blacklist.register(self.peer.host, True)


class IrccatFactory(protocol.Factory):
    ''' Twisted factory producing a Protocol using buildProtocol. '''

    def __init__(self, irc, config_, blacklist):
        self.irc = irc
        self.config = config_
        self.blacklist = blacklist

    def buildProtocol(self, addr):
        return IrccatProtocol(self.irc, self.config, self.blacklist)


class Irccat(callbacks.Plugin):
    '''
    Main plugin.

    Runs the dataflow from TCP port -> irc in a separate thread,
    governed bu twisted's reactor.run(). Commands are executed in
    main thread. The critical zone is self.config, a _Config instance.
    '''
    # pylint: disable=E1101,R0904

    threaded = True
    admin = 'owner'       # The capability required to manage data.

    def __init__(self, irc):
        callbacks.Plugin.__init__(self, irc)
        self.config = _Config()
        self.blacklist = _Blacklist()
        factory = IrccatFactory(irc, self.config, self.blacklist)
        self.server = reactor.listenTCP(self.config.port, factory)
        self.thread = \
            threading.Thread(target = reactor.run,
                             kwargs = {'installSignalHandlers': False})
        self.thread.start()

    def die(self):
        ''' Tear down reactor thread and die. '''
        reactor.callFromThread(reactor.stop)
        self.thread.join()
        callbacks.Plugin.die(self)

    def sectiondata(self, irc, msg, args, section_name, password, channels):
        """ <section name> <password> <channel[,channel...]>

        Update a section with name, password and a comma-separated list
        of channels which should be connected to this section. Creates
        new section if it doesn't exist.
        """

        self.config.update(section_name, password, channels)
        irc.replySuccess()

    sectiondata = wrap(sectiondata, [admin,
                                     'somethingWithoutSpaces',
                                     'somethingWithoutSpaces',
                                     commalist('validChannel')])

    def sectionkill(self, irc, msg, args, section_name):
        """ <section name>

        Removes an existing section given it's name.
        """

        try:
            self.config.remove(section_name)
        except KeyError:
            irc.reply("Error: no such section")
            return
        irc.replySuccess()

    sectionkill = wrap(sectionkill, [admin, 'somethingWithoutSpaces'])

    def sectionshow(self, irc, msg, args, section_name):
        """ <section name>

        Show data for a section.
        """

        try:
            password, channels = self.config.get(section_name)
        except KeyError:
            irc.reply("Error: no such section")
            return
        msg = password + ' ' + ','.join(channels)
        irc.reply(msg)

    sectionshow = wrap(sectionshow, [admin, 'somethingWithoutSpaces'])

    def sectionlist(self, irc, msg, args):
        """ <takes no arguments>

        Print list of sections.
        """
        msg = ' '.join(self.config.keys())
        irc.reply(msg if msg else 'No sections defined')

    sectionlist = wrap(sectionlist, [admin])

    def sectionhelp(self, irc, msg, args):
        """ <takes no argument>

        print help url
        """
        irc.reply(_HELP_URL)

    sectionhelp = wrap(sectionhelp, [])


Class = Irccat


# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:
