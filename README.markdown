# Twitter Spy

TwitterSpy is a supplemental bot for twitter that does the stuff the twitter
one used to do, and a few things it doesn't.

# Usage

IM `help` to [twitterspy@jabber.org](xmpp:twitterspy@jabber.org) to see what
you can do.

# When Messages Cease

Twitterspy will stop doing work for you, and stop sending you messages under
the following conditions:

* You are not logged in to your XMPP server.
* You are logged in with a negative priority.
* You are logged in with your XMPP status as `xa` (extended away) or `dnd` (do not disturb)
* You have specifically disabled the service via the "off" command.

# Running Your Own Instance

It's easy to run your own instance.  You'll need a recent version of
[twisted](http://twistedmatrix.com/trac/) (specifically names, web, and words),
and an item from the [cheese shop](http://www.python.org/pypi):

* SQLAlchemy

You can install the SQLAlchemy using <code>easy\_install</code>:

    easy_install SQLAlchemy
