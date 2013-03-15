Supybot Irccat Plugin
=====================
This is a plugin for the IRC bot Supybot that introduces the ability to
listen to a TCP port and relay incoming text to one or more IRC channels,
using some primitive security mechanisms.

Dependencies
------------
- python-twisted (tested with 12.1)
- supybot (tested with 0.83.4)

Getting started
---------------
* Refer to the supybot documentation to install supybot and configure
  your server e. g., using supybot-wizard. Verify that you can start and
  contact your bot.

* Unpack the plugin into the plugins directory (created by
  supybot-wizard):
```
      $ cd plugins
      $ git clone https://github.com/leamas/supybot-irccat Irccat
```

* Restart the server and use `@list` to verify that the plugin is loaded:
```
    <leamas> @list
    <al-bot-test> leamas: Admin, Channel, Config, Irccat, Owner, and User
```

* Identify yourself for the bot in a *private window*. Creating user +
  password is part of the supybot-wizard process.
```
     <leamas> identify al my-secret-pw
     <al-bot-test> The operation succeeded.
```
* Define the port you want to use as listener port (still in private window):
```
     <leamas> config plugins.irccat.port 12345
     <al-bot-test> The operation succeeded.
```

* In order to use irccat you need to define a section. A section has a name,
  a password and a list of channels to feed. Define your first section
  named foo with password pwfoo sending data to the channel #al-bot-test:
```
    <leamas> sectiondata foo pwfoo #al-bot-test
    <al-bot-test> leamas: The operation succeeded.
```

* The lines sent to irccat should be formatted like
 `section;password; some text to show`. To test, send such a line using nc:
```
    $ echo "foo;pwfoo;footext to show" | nc  --send-only localhost 12345
    $
```
In the selected channel you will see:
```
    *al-bot-test* footext to show
```

Configuration
-------------

The configuration is done completely in IRC. There are general settings
and section specific ones. To see the general settings:
```
    @config list plugins.irccat
    leamas:  port, public, and sectionspath
```

Each general setting has help info and could be inspected and set using
the config plugin, see it's documents. Quick crash course using port as
example:

* Getting help: `@config help plugins.irccat.port`
* See actual value: `@config plugins.irccat.port`
* Setting value: `@config plugins.irccat.port 6060`

The `public`, option is internal, please don't touch.

NOTE! After modifying the variables use `@reload Irccat` to make them
effective.

The available sections can be listed using
```
    <leamas> sectionlist
    <al-bot-test> yngve ivar
```

To see actual settings:
```
    @sectionshow ivar
    leamas: ivar #al-bot-test
```

These variables can be manipulated using `sectiondata` as explained in Getting Started.


Input line format
-----------------
Each line read from the input port should have the following format:

    <name>;<password>;<any text>

- name: The name of a configuration section i. e., a value from
  `@sectionlist`.
- password: As defined in the configuration section, use
   `@sectionshow <section name>` to display.
- The text after the second ';' is sent verbatim to the channel(s) listed
  in the section.

Unparsable lines are logged but otherwise silently dropped. Blacklisted
clients are not even logged.


Command List
------------
* `sectiondata`: Takes a section name, a password and a comma-separated
   list of channels to feed. Creates section if it doesn't exist.

* `sectionkill`: Delete a section given it's name.

* `sectionlist`: List available sections.

* `sectionshow`: Show password and channels for a section.

* `config plugins.irccat.port`: Show  the TCP port irccat listens to.


Security
--------
Irc servers are normally not Fort Knox, so this is not the place for ssl or
2-factor authentication. That said, leaving a TCP port open as a relay to
irc channel(s) certainly requires some precaution. The steps here are:

- The client must know the section and it's password as described above.
- Managing passwords requires 'owner' capability in irc.
- Clients which repeatedly fails to send correct data are blacklisted for a
  while.


Static checking
---------------

pep8 (in the Git directory):
```
  $ pep8 --config pep8.conf . > pep8.log
```
pylint: (in the Git directory):
```
  $ pylint --rcfile pylint.conf \*.py > pylint.log
```
Unit tests are currently not in place.
