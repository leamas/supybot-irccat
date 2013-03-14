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

from twisted.internet import reactor, protocol
from twisted.protocols import basic

from supybot import callbacks
#from supybot import ircutils
from supybot import ircmsgs
#from supybot import log
#from supybot import plugins
#from supybot import utils
from supybot.commands import threading

import config


class IrccatProtocol(basic.LineOnlyReceiver):
    ''' Line protocol: parse line, forward to channel(s). '''
    delimiter = '\n'

    def __init__(self, irc):
        self.irc = irc

    def lineReceived(self, text):
        ''' Handle one line of input from client. '''
        self.irc.queueMsg(ircmsgs.notice('#al-bot-test', text))


class IrccatFactory(protocol.Factory):
    ''' Twisted factory producing a Protocol using buildProtocol. '''

    def __init__(self, irc):
        self.irc = irc

    def buildProtocol(self, addr):
        return IrccatProtocol(self.irc)


class Irccat(callbacks.Plugin):
    ''' Main plugin. '''
    # pylint: disable=E1101,R0904

    threaded = True

    def __init__(self, irc):
        callbacks.Plugin.__init__(self, irc)
        port = config.global_option('port').value
        self.server = reactor.listenTCP(port, IrccatFactory(irc))
        kwargs_ = {'installSignalHandlers': False}
        self.thread = threading.Thread(target = reactor.run, kwargs = kwargs_)
        self.thread.start()

    def die(self):
        ''' Tear down reactor thread and die. '''
        reactor.callFromThread(reactor.stop)
        self.thread.join()
        callbacks.Plugin.die(self)

Class = Irccat


# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:
