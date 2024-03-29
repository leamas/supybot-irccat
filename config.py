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

###

''' Plugin registry initialization and access. '''

import supybot.conf as conf
import supybot.registry as registry


def configure(advanced):
    ''' Not used ATM '''
    # This will be called by supybot to configure this module.  advanced is
    # a bool that specifies whether the user identified himself as an advanced
    # user or not.  You should effect your configuration by manipulating the
    # registry as appropriate.
    ### from supybot.questions import expect, anything, something, yn
    conf.registerPlugin('Irccat', True)


def global_option(option):
    ''' Return a overall plugin option (registered at load time). '''
    return conf.supybot.plugins.get('irccat').get(option)


# This is where your configuration variables (if any) should go.  For example:
# conf.registerGlobalValue(Irccat, 'someConfigVariableName',
#     registry.Boolean(False, """Help for someConfigVariableName."""))

Irccat = conf.registerPlugin('Irccat')

conf.registerGlobalValue(Irccat, 'sectionspath',
    registry.String('sections.pickle', 'Pickled section data'))

conf.registerGlobalValue(Irccat, 'port',
    registry.NonNegativeInteger(12345,
                                "The TCP port irccat will listen to."))

conf.registerGlobalValue(Irccat, 'interface',
    registry.String("127.0.0.1",
                    "The address irccat will bind to."))

conf.registerGlobalValue(Irccat, 'privmsg',
    registry.Boolean(False, 'Use privmsgs instead of the default notices'))

# vim:set shiftwidth=4 tabstop=4 expandtab textwidth=79:
