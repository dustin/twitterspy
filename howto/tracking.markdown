---
layout: default
title: HOWTO - Tracking - dustin/twitterspy @ GitHub
---

## Tracking Topics

The most powerful feature of twitterspy is found in tracking.
Tracking allows you to see when people are talking about things or
people you find interesting.

In the most simple case, you can track a word by just typing in the
word of interest to the `track` command:

    track memcached

With this, whenever anyone mentions "memcached" in a tweet, you'll
receive an IM.  It's that easy.

If you get tired of hearing about a particular topic, you can untrack
it with the `untrack` command:

    untrack boring

At any point, you can get a list of topics you're tracking with the
`tracks` command:

    tracks

## Advanced Tracking

twitterspy's track is powered by [twitter search][search], so you can
do anything here you can do there, but without having to keep browser
tabs open, or even remember about all of the little things you have
found interesting.

In particular, all of the [search operators][operators] are supported,
so if you're interested in hearing about xmpp, but you think things I
have to say about it are too boring, you can listen to only what other
people have to say about it:

    track zfs -from:dlsspy

[search]: http://search.twitter.com/
[operators]: http://search.twitter.com/operators
