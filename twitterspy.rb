#!/usr/bin/env ruby

require 'rubygems'
require 'sqlite3'
require 'date'
require 'xmpp4r-simple'

require 'twitterspy/config'
require 'twitterspy/models'
require 'twitterspy/commands'
require 'twitterspy/threading'


class GlobalStats
  include Singleton
  attr_accessor :user_count
end

def process_xmpp_incoming(server)
  server.presence_updates do |user, status, message|
    User.update_status user, status
  end
  # Called for dequeue side-effect stupidity of jabber:simple
  server.received_messages
  server.new_subscriptions do |from, presence|
    puts "Subscribed by #{from}"
  end
  server.subscription_requests do |from, presence|
    puts "Sub req from #{from}"
  end
end

def process_message(server, msg)
  cmd, args = msg.body.split(' ', 2)
  cp = TwitterSpy::Commands::CommandProcessor.new server
  user = User.first(:jid => msg.from.bare.to_s) || User.create(:jid => msg.from.bare.to_s)
  cp.dispatch cmd, user, args
end

def update_status(server)
  users = User.count
  stats = GlobalStats.instance
  if users != stats.user_count
    puts "Updating status with #{users} users"
    $stdout.flush
    stats.user_count = users
    status = "Looking at stuff for #{users} users"
    server.send!(Jabber::Presence.new(nil, status,
      TwitterSpy::Config::CONF['xmpp'].fetch('priority', 1).to_i))
  end
end

def run_loop(server)
  process_xmpp_incoming server
  sleep TwitterSpy::Config::LOOP_SLEEP
rescue StandardError, Interrupt
  puts "Got exception:  #{$!.inspect}\n#{$!.backtrace.join("\n\t")}"
  $stdout.flush
  sleep 5
end

def inner_loop(server)
  loop do
    run_loop server
  end
end

TwitterSpy::Config::CONF['general'].fetch('nthreads', 1).to_i.times do |t|
  puts "Starting thread #{t}"
  TwitterSpy::Threading.start_worker
end

loop do
  puts "Connecting..."
  $stdout.flush
  server = Jabber::Simple.new(
    TwitterSpy::Config::CONF['xmpp']['jid'],
    TwitterSpy::Config::CONF['xmpp']['pass'])
  # A lower-level hook to provide more realtime message processing.
  server.client.add_message_callback do |message|
    begin
      process_xmpp_incoming server
      update_status server
      process_message server, message unless message.body.nil?
    rescue StandardError, Interrupt
      puts "Incoming message error:  #{$!}"
      $stdout.flush
      server.deliver message.from, "Error processing your message:  #{$!}"
    end
  end

  update_status(server)

  puts "Set up with #{server.inspect}"
  $stdout.flush
  inner_loop server
end
