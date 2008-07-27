#!/usr/bin/env ruby

require 'rubygems'
require 'sqlite3'
require 'date'
require 'summize'
require 'htmlentities'

require 'twitterspy/config'
require 'twitterspy/models'
require 'twitterspy/commands'
require 'twitterspy/threading'
require 'twitterspy/delivery_helper'
require 'twitterspy/main'

TwitterSpy::Config::CONF['general'].fetch('nthreads', 1).to_i.times do |t|
  puts "Starting general thread #{t}"
  TwitterSpy::Threading.start_worker TwitterSpy::Threading::IN_QUEUE
end
TwitterSpy::Config::CONF['general'].fetch('twitrthreads', 1).to_i.times do |t|
  puts "Starting twitter read thread #{t}"
  TwitterSpy::Threading.start_worker TwitterSpy::Threading::TWIT_R_QUEUE
end
TwitterSpy::Config::CONF['general'].fetch('twitwthreads', 1).to_i.times do |t|
  puts "Starting twitter write thread #{t}"
  TwitterSpy::Threading.start_worker TwitterSpy::Threading::TWIT_W_QUEUE
end

def inner_loop(main)
  loop do
    main.run_loop
  end
end

loop do
  puts "Connecting..."
  $stdout.flush
  Jabber::debug=true
  inner_loop TwitterSpy::Main.new
end
