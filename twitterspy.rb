#!/usr/bin/env ruby

require 'rubygems'
require 'sqlite3'
require 'date'
require 'xmpp4r-simple'
require 'summize'

require 'twitterspy/config'
require 'twitterspy/models'
require 'twitterspy/commands'
require 'twitterspy/threading'

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
  cmd, args = msg.body.gsub('&quot;', '"').split(' ', 2)
  cp = TwitterSpy::Commands::CommandProcessor.new server
  user = User.first(:jid => msg.from.bare.to_s) || User.create(:jid => msg.from.bare.to_s)
  cp.dispatch cmd, user, args
end

def update_status(server)
  users = User.count
  tracks = Track.count
  puts "Updating status with #{users} users and #{tracks} tracks"
  status = "Tracking #{tracks} topics for #{users} users"
  server.send!(Jabber::Presence.new(nil, status,
    TwitterSpy::Config::CONF['xmpp'].fetch('priority', 1).to_i))
end

def process_tracks(server)
  TwitterSpy::Threading::IN_QUEUE << Proc.new do
    outbound=Hash.new { |h,k| h[k] = {}; h[k] }
    Track.todo(TwitterSpy::Config::WATCH_FREQ).each do |track|
      puts "Fetching #{track.query} at #{Time.now.to_s}"
      summize_client = Summize::Client.new 'twitterspy@jabber.org'
      begin
        oldid = track.max_seen.to_i
        res = summize_client.query track.query, :since_id => oldid
        track.update_attributes(:last_update => DateTime.now, :max_seen => res.max_id)
        totx = oldid == 0 ? Array(res).last(5) : res.select { |x| x.id.to_i > oldid }
        track.users.select{|u| u.available? }.each do |user|
          totx.each do |msg|
            if user.language.nil? || msg.language.nil? || user.language == msg.language
              outbound[user.jid][msg.id] = msg if msg.id.to_i > user.min_id
            end
          end
        end
      rescue StandardError, Interrupt
        puts "Error fetching #{track.query}: #{$!}"
      end
    end
    outbound.each do |jid, msgs|
      puts "Sending #{msgs.size} messages to #{jid}"
      msgs.keys.sort.each do |msgk|
        msg = msgs[msgk]
        server.deliver jid, "#{msg.from_user}: #{msg.text}"
      end
    end
  end
end

def run_loop(server)
  process_xmpp_incoming server
  puts "Processing..."
  update_status server
  process_tracks server
  $stdout.flush
  sleep TwitterSpy::Config::LOOP_SLEEP
  repository(:default).adapter.query(
    "delete from tracks where id not in (select track_id from user_tracks)"
  )
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
      process_message server, message unless message.body.nil?
    rescue StandardError, Interrupt
      puts "Incoming message error:  #{$!}\n" + $!.backtrace.join("\n\t")
      $stdout.flush
      server.deliver message.from, "Error processing your message:  #{$!}"
    end
  end

  update_status(server)

  puts "Set up with #{server.inspect}"
  $stdout.flush
  inner_loop server
end
