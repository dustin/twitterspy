#!/usr/bin/env ruby

require 'twitterspy/config'
require 'twitterspy/models'

puts "Migrating..."
DataMapper.auto_migrate!