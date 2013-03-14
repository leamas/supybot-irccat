Supybot Irccat Plugin
=====================
This is a plugin for the IRC bot Supybot that introduces the ability to
listen to a TCP port and relay incoming text to one or more IRC channels

Dependencies
------------
There's nothing special besides python 2.x (tested using 2.7), twisted
and supybot.

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
    <leamas> @addsection foo pwfoo #al-bot-test
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

The configuration is done completely in the supybot registry. There are general
settings and section specific ones.

To see the general settings:
```
    @config list plugins.irccat
    leamas: @sections, sectionlist, public, and port
```

Each setting has help info and could be inspected and set using the config
plugin, see it's documents. Quick crash course using port as example:
* Getting help: `@config help plugins.irccat.port`
* See actual value: `@config plugins.irccat.port`
* Setting value: `@config plugins.irccat.port 60`

The `public`, `sections` and `sectionlist` options are internal, please don't touch.
So, just use the port option here.

The available sections can be listed using
```
    @config list plugins.irccat.sections
    leamas: @test1, @test2, and @test3
```

Settings for each section are below these. To see available settings:
```
    @config list plugins.irccat.sections.test1
    leamas: password, and channels
```

These variables can be manipulated using the @config command in the same way.
NOTE! After modifying the variables use `@reload Irccat` to make them
effective.

It's possible to edit the config file "by hand" as described in documentation
for @config. However, structural changes are better done using `addsection`
and `killsection` even if the config  file is edited after that.

Input line format
-----------------
Each line read from the input port should have the following format:

    <name>;<password>;<any text>

- name: The name of a configuration section i. e., a value from
  `@config list plugins.irccat.sections`.
- password: As defined in the configuration section, use
   `@config plugins.irccat.sections.<section name>.password` to display.
- The text after the second ';' is sent verbatim to the channel(s) listed
  in the section.

Unparsable lines are logged but otherwise silently dropped.


Command List
------------

* `addsection`: Takes a section name, a password and a comma-separated
   list of channels to feed.

* `killsection`: Delete a section given it's name.

* `config list plugins.irccat.sections`: List available sections

* `config plugins.irccat.port`: Show  the TCP port irccat listens to.

* `config plugins.irccat.sections.foo.password`: Show password for section 'foo'.

* `config plugins.irccat.sections.foo.channels`: Show channels for section 'foo'.

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
