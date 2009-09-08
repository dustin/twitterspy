---
layout: default
title: HOWTO - Disabling - dustin/twitterspy @ GitHub
---

## Ceasing Twitterspy Traffic

Twitterspy will not send you messages at all if any one of the
following is true:

* You are not logged in to your XMPP server (or are invisible).
* You are logged in with a negative priority.
* You are logged in with your XMPP status as `xa` (extended away) or
  `dnd` (do not disturb).
* You have specifically disabled the service via the `off` command.

## Disabling Twitterspy Completely

When in doubt, the following should make all traffic stop:

    off

## Disabling Friend Watching

If it's just friend and direct traffic you'd like to stop, the
following will do it:

    watch_friends off

## Disabling a Specific Track

If you're getting too many track matches from a particular topic, you
can disable that topic with the `untrack` command:

    untrack annoying topic

## Disabling Part of a Specific Track

If a particular tracked topic is getting flooded by a spammer, you can
recreate it with negative keywords to keep spammers/flooders away.

For example, if you've been tracking "github", but don't want to see
all the commits, you can do the following:

    untrack github
    track github -commit
