#!/usr/bin/env python

import sys
sys.path.append('lib')
sys.path.append('../lib')

import models

models._engine.execute("alter table users add column created_at timestamp")
