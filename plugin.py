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

'''
Main plugin module. See README for usage and configuration.

Here is two processes, the main process and the io_process.
The main process has a separate listener_thread.

The io_process gets data from a port and forwards it to the
main process. The main process handles user commands. A separate
thread gets data from the io_process and forwards to irc.

Somewhat messy. Design effected by need to run twisted in a process
so it vcan be restarted, and that the irc state can't be shared
i. e., the separate process can't shuffle data to irc.

Here are no critical zones, this is pure message passing. The
io_process gets updated configurations from main. Main gets data
to print from io_process.
 '''

import crypt
import multiprocessing
import pickle
import random
import re
import sys
import time

from twisted.internet import reactor, protocol
from twisted.protocols import basic

from supybot import callbacks
from supybot import ircmsgs
from supybot import log
from supybot import world
from supybot.commands import commalist
from supybot.commands import threading
from supybot.commands import wrap

from . import config


_HELP_URL = "https://github.com/leamas/supybot-irccat"


def io_process(port, pipe):
    ''' Run the twisted-governed data flow from port -> irc. '''
    # pylint: disable=E1101

    logger = log.getPluginLogger('irccat.io')
    logger.debug("Starting IO process on %d" % port)
    reactor.listenTCP(port, IrccatFactory(pipe))
    try:
        reactor.run()
    except Exception as ex:                          # pylint: disable=W0703
        logger.error("Exception in io_process: " + str(ex), exc_info = True)
    logger.info(" io_process: exiting")


class _Blacklist(object):
    ''' Handles blacklisting of faulty  clients. '''

    FailMax = 8   # Max # of times
    BlockTime = 500  # Time we wait in blacklisted state (seconds).

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


class _Section(object):
    ''' Section representation in _Config._data. '''

    def __init__(self, password, channels):
        self.password = password
        self.channels = channels


class _Config(object):
    ''' Persistent stored section data. '''

    def __init__(self):
        self.port = config.global_option('port').value
        self.privmsg = config.global_option('privmsg').value
        self.topic_regex = config.global_option('topicRegex').value
        self._path = config.global_option('sectionspath').value
        try:
            self._data = pickle.load(open(self._path, 'rb'))
        except IOError:
            self._data = {}
            logger = log.getPluginLogger('irccat.config')
            logger.warning("Can't find stored config, creating empty.")
            self._dump()
        except Exception:   # Unpickle throws just anything.
            self._data = {}
            logger = log.getPluginLogger('irccat.config')
            logger.warning("Bad stored config, creating empty.")
            self._dump()

    def _dump(self):
        ''' Update persistent data.'''
        pickle.dump(self._data, open(self._path, 'wb'))

    def get(self, section_name):
        ''' Return (password, channels) tuple or raise KeyError. '''
        s = self._data[section_name]
        return s.password, s.channels

    def update(self, section_name, password, channels):
        ''' Store section data for name, creating it if required. '''
        self._data[section_name] = _Section(password, channels)
        self._dump()

    def remove(self, section_name):
        ''' Remove existing section or raise KeyError. '''
        del(self._data[section_name])
        self._dump()

    def keys(self):
        ''' Return list of section names. '''
        return list(self._data.keys())


class IrccatProtocol(basic.LineOnlyReceiver):
    ''' Line protocol: parse line, forward to channel(s). '''

    delimiter = b'\n'

    def __init__(self, config_, blacklist, msg_conn):
        self.config = config_
        self.blacklist = blacklist
        self.msg_conn = msg_conn
        self.peer = None
        self.log = log.getPluginLogger('irccat.protocol')

    def connectionMade(self):
        self.peer = self.transport.getPeer()
        if self.blacklist.onList(self.peer.host):
            self.transport.abortConnection()

    def connectionLost(self, reason):            # pylint: disable=W0222
        self.peer = None

    def lineReceived(self, text):
        ''' Handle one line of input from client. '''

        def warning(what):
            ''' Log and register bad input warning. '''
            if self.peer:
                what += ' from: ' + str(self.peer.host)
            self.log.warning(what)
            if world.testing:
                self.msg_conn.send((what, ['#test']))
            self.blacklist.register(self.peer.host, False)

        try:
            if sys.version_info[0] >= 3:
                text = text.decode()
        except UnicodeDecodeError:
            warning('Invalid encoding: ' + repr(text))
            return

        try:
            section, cleartext_pw, data = text.split(';', 2)
        except ValueError:
            warning('Illegal format: ' + text)
            return
        try:
            cipher_pw, channels = self.config.get(section)
        except KeyError:
            warning("No such section: " + section)
            return
        if crypt.crypt(cleartext_pw, cipher_pw) != cipher_pw:
            warning('Bad password: ' + cleartext_pw)
            return
        if not channels:
            warning('Empty channel list: ' + section)
        self.log.debug("Sending " + data + " to: " + str(channels))
        self.msg_conn.send((data, channels))
        self.blacklist.register(self.peer.host, True)


class IrccatFactory(protocol.Factory):
    ''' Twisted factory producing a Protocol using buildProtocol. '''

    def __init__(self, pipe):
        self.pipe = pipe
        self.blacklist = _Blacklist()
        assert self.pipe[0].poll(), "No initial config!"
        self.config = self.pipe[0].recv()

    def buildProtocol(self, addr):
        if self.pipe[0].poll():
            self.config = self.pipe[0].recv()
        return IrccatProtocol(self.config, self.blacklist, self.pipe[0])


class Irccat(callbacks.Plugin):
    '''
    Main plugin.

    Runs the dataflow from TCP port -> irc in a separate thread,
    governed by twisted's reactor.run(). Commands are executed in
    main thread. The critical zone is self.config, a _Config instance.
    '''
    # pylint: disable=E1101,R0904

    threaded = True
    admin = 'owner'       # The capability required to manage data.

    def __init__(self, irc):
        callbacks.Plugin.__init__(self, irc)
        self.log = log.getPluginLogger('irccat.irccat')
        self.config = _Config()

        self.pipe = multiprocessing.Pipe()
        self.pipe[1].send(self.config)
        self.process = multiprocessing.Process(
                            target = io_process,
                            args = (self.config.port, self.pipe))
        self.process.start()

        self.listen_abort = False
        self.thread = threading.Thread(target = self.listener_thread)
        self.thread.start()

    def replace_topic(self, irc, channel, pattern, replacement):
        """
        Looks for pattern in channel topic and replaces it with replacement
        string.
        """
        curtopic = irc.state.getTopic(channel)
        newtopic = re.sub(pattern, lambda m: replacement, curtopic, count=1,
                          flags=re.IGNORECASE)
        irc.queueMsg(ircmsgs.topic(channel, newtopic))

    def listener_thread(self):
        ''' Take messages from process, write them to irc.'''
        while not self.listen_abort:
            try:
                if not self.pipe[1].poll(0.5):
                    continue
                msg, channels = self.pipe[1].recv()
                for channel in channels:
                    for irc in world.ircs:
                        if channel in irc.state.channels:
                            if self.config.topic_regex:
                                self.replace_topic(irc, channel,
                                                   self.config.topic_regex, msg)
                            elif self.config.privmsg:
                                irc.queueMsg(ircmsgs.privmsg(channel, msg))
                            else:
                                irc.queueMsg(ircmsgs.notice(channel, msg))
                        else:
                            self.log.warning(
                                "Can't write to non-joined channel: " + channel)
            except EOFError:
                self.listen_abort = True
            except Exception:
                self.log.debug("LISTEN: Exception", exc_info = True)
                self.listen_abort = True
        self.log.debug("LISTEN: exiting")

    def die(self, cmd = False):                   # pylint: disable=W0221
        ''' Tear down reactor thread and die. '''

        self.log.debug("Dying...")
        self.process.terminate()
        self.listen_abort = True
        self.thread.join()
        if not cmd:
            callbacks.Plugin.die(self)

    def sectiondata(self, irc, msg, args, section_name, password, channels):
        """ <section name> <password> <channel[,channel...]>

        Update a section with name, password and a comma-separated list
        of channels which should be connected to this section. Creates
        new section if it doesn't exist.
        """
        salts = 'abcdcefghijklmnopqrstauvABCDEFGHIJKLMNOPQRSTUVXYZ123456789'

        salt = random.choice(salts) + random.choice(salts)
        cipher_pw = crypt.crypt(password, salt)
        self.config.update(section_name, cipher_pw, channels)
        self.pipe[1].send(self.config)
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
        self.pipe[1].send(self.config)
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
