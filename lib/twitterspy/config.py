#!/usr/bin/env python
"""
Configuration for twitterspy.

Copyright (c) 2008  Dustin Sallings <dustin@spy.net>
"""

import ConfigParser
import commands

CONF=ConfigParser.ConfigParser()
CONF.read('twitterspy.conf')
VERSION=commands.getoutput("git describe").strip()
ADMINS=CONF.get("general", "admins").split(' ')
