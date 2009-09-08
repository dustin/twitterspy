---
layout: default
title: HOWTO - Introduction - dustin/twitterspy @ GitHub
---

# Getting Started

The first thing you need to do is add
[im@twitterspy.org](xmpp:im@twitterspy.org) to your roster:

<img alt="im@twitterspy.org" src="images/AddContact.png" />

## Posting

In order to post, follow, leave, etc... you must first login.  You do
this by IMming the following message:

    twlogin yourusername yourpassword

After a successful login, you can post using the `post` command as
follows:

    post Hey look, I'm posting from twitterspy.

twitterspy will tell you when you have successfully posted a message.

As a shortcut, if your message begins with @, it's always assumed to
be a post:

    @dlsspy Look at me responding to a post.

## Autopost

Though it's not recommended, you can post without having to start
every post with the `post` by enabling autopost using `autopost on`.

Any text you enter that cannot be recognized as a command will be
blasted to twitter.  Some people really like this.  Personally, I find
it dangerous.

