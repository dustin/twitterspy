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
* [SQLAlchemy][sqlalchemy]
* [Memcached][memcached]

## Install

1. Install dependencies
2. git submodule init &amp;&amp; git submodule update
3. copy twitterspy.conf.sample to twitterspy.conf
4. edit twitterspy.conf
5. ./etc/create\_tables.py
6. twistd -ny twitterspy.tac

Do note that this service expects memcached to be running on localhost
on whatever machine is running the bot.  memcached is used for
optimistic message deduplication, but is required for operation.  The
errors you get when memcached is not running are currently a bit
weird (something about 'NoneType' object has no attribute 'add').

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

[1]:http://github.com/dustin/twitterspy/zipball/master
[2]:http://github.com/dustin/twitterspy/tarball/master
[twisted]:http://twistedmatrix.com/
[sqlalchemy]:http://www.sqlalchemy.org/
[memcached]:http://www.danga.com/memcached/
