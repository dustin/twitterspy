---
layout: default
title: HOWTO - Following - dustin/twitterspy @ GitHub
---

## Getting Started with Following

If you are logged in, you may use twitter's follow and unfollow
features as well as blocking and unblocking.  Please see the
[introduction][intro] for more information about logging in.

Note that twitterspy will not by default show you tweets from your
friends.  In order to do that, you must tell it you're interested in
receiving those:

    watch_friends on

If you find this traffic uninteresting, you can disable it again as
follows:

    watch_friends off

## Following and Unfollowing Users

You can follow a user using the `follow` command.  For example:

    follow dlsspy

To stop following a user, use the `leave` command:

    leave stupidspammer

## Blocking and Unblocking Users

To block a user, use the `block` command:

    block stupidspammer

To unblock a user, use the `unblock` command:

    unblock notstupidspammer

[intro]: intro.html
