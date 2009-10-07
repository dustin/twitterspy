---
layout: default
title: dustin/twitterspy @ GitHub -- developer page
---

<div class="download">
  <a href="http://github.com/dustin/twitterspy/zipball/master">
    <img alt="zip" width="90"
	src="http://github.com/images/modules/download/zip.png"/></a>
  <a href="http://github.com/dustin/twitterspy/tarball/master">
  <img alt="tar" width="90"
	src="http://github.com/images/modules/download/tar.png"/></a>
</div>

## Dependencies
* [Twisted][twisted] (names, web, words)
* [Memcached][memcached]
* python-oauth (`easy_install oauth`)

## Install

1. Install dependencies
2. git submodule init &amp;&amp; git submodule update
3. copy twitterspy.conf.sample to twitterspy.conf
4. edit twitterspy.conf

### DB Setup

There are a couple database options.  Some basic instructions follow:

#### CouchDB

My twitterspy instance `im@twitterspy.org` runs on couchdb.  Setup
is pretty straightforward.  Grab a version of [couchdb][couchdb] and
edit `twitterspy.conf` to look like this:

    [db]
    type: couch
    host: localhost

`localhost` should obviously be replaced with the location of your
couchdb server.

After configuring up the db, run the following command to create your
database:

    ./etc/create_couch.py

#### SQL

If you'd like to use sqlite instead of couchdb for a more simple
install, you can configure `twitterspy.conf` thusly:

    [db]
    type: sql
    driver: sqlite3
    args: ['/path/to/twitterspy.sqlite3']

This would theoretically work with another SQL-based database, but
it's only been tested in sqlite and there are most certainly bugs.

To bootstrap your schema, run the following command:

    sqlite3 /path/to/twitterspy.sqlite3 < etc/schema.sql

## Running

Foreground execution:

    twistd -ny twitterspy.tac

Background execution:

    twistd -y twitterspy.tac

Do note that this service expects memcached to be running on localhost
on whatever machine is running the bot.  memcached is used for
optimistic message deduplication, but is required for operation.  The
errors you get when memcached is not running are currently a bit
weird (something about 'NoneType' object has no attribute 'add').

## Help from Others

[David Banes](http://www.davidbanes.com/) was kind enough to write an
article about his adventures in [getting twitterspy running on debian][tsdeb].

## License

[MIT](http://www.opensource.org/licenses/mit-license.php)

## Authors

<ul>
	<li>Dustin Sallings (dustin@spy.net)</li>
	<li class="minor">tsing (tsing@jianqing.org)</li>
	<li class="minor">Klaus Alexander Seistrup (klaus@seistrup.dk)</li>
	<li class="minor">Pedro Melo (melo@simplicidade.org)</li>
	<li class="minor">Stefan Strigler (zeank@fiddl.strigler.de)</li>
</ul>

## Contact

Dustin Sallings (dustin@spy.net)

## Download

You can download this project in either [zip][1] or [tar][2] formats.

You can also clone the project with [git](http://git-scm.com/) by running:

    $ git clone git://github.com/dustin/twitterspy.git
    $ cd twitterspy
    $ git submodule init
    $ git submodule update

[1]:http://github.com/dustin/twitterspy/zipball/master
[2]:http://github.com/dustin/twitterspy/tarball/master
[twisted]:http://twistedmatrix.com/
[memcached]:http://www.danga.com/memcached/
[tsdeb]:http://www.davidbanes.com/2009/01/11/installing-twitterspy-on-debian-etch/
[couchdb]:http://couchdb.apache.org/
