require 'xmpp4r'
require 'xmpp4r/roster'

require 'twitterspy/tracker'
require 'twitterspy/user_info'
require 'twitterspy/delivery_helper'

module TwitterSpy

  class Main

    include TwitterSpy::DeliveryHelper

    def initialize
      @users = 0
      @tracks = 0

      jid = Jabber::JID.new(TwitterSpy::Config::CONF['xmpp']['jid'])
      @client = Jabber::Client.new(jid)
      @client.connect
      @client.auth(TwitterSpy::Config::CONF['xmpp']['pass'])
      register_callbacks
      subscribe_to_unknown

      update_status
    end

    def subscribe_to(jid)
      puts "Sending subscription request to #{jid}"
      req = Jabber::Presence.new.set_type(:subscribe)
      req.to = jid
      @client.send req
    end

    def subscribe_to_unknown
      User.all(:status => nil).each {|u| subscribe_to u.jid}
      $stdout.flush
    end

    def register_callbacks
      @roster = Jabber::Roster::Helper.new(@client)

      @roster.add_subscription_request_callback do |roster_item, presence|
        puts "Accepting subscription request from #{presence.from}"
        @roster.accept_subscription(presence.from)
      end

      @client.add_presence_callback do |presence|
        status = presence.type.nil? ? :available : presence.type
        User.update_status presence.from.bare.to_s, status
      end

      @client.add_message_callback do |message|
        begin
          process_message message unless message.body.nil?
        rescue StandardError, Interrupt
          puts "Incoming message error:  #{$!}\n" + $!.backtrace.join("\n\t")
          $stdout.flush
          deliver message.from, "Error processing your message:  #{$!}"
        end
      end
    end

    def process_message(msg)
      decoded = HTMLEntities.new.decode(msg.body).gsub(/&/, '&amp;')
      cmd, args = decoded.split(' ', 2)
      cp = TwitterSpy::Commands::CommandProcessor.new @client
      user = User.first(:jid => msg.from.bare.to_s) || User.create(:jid => msg.from.bare.to_s)
      cp.dispatch cmd.downcase, user, args
    end

    def update_status
      users = User.count
      tracks = Track.count
      if users != @users || tracks != @tracks
        status = "Tracking #{tracks} topics for #{users} users"
        puts "Updating status:  #{status}"
        @client.send(Jabber::Presence.new(nil, status,
          TwitterSpy::Config::CONF['xmpp'].fetch('priority', 1).to_i))
        @users = users
        @tracks = tracks
      end
    end

    def process_tracks
      TwitterSpy::Threading::IN_QUEUE << Proc.new do
        TwitterSpy::Tracker.new(@client).update
      end
    end

    def process_user_specific
      User.all(:active => true, :username.not => nil,
        :status.not => ['dnd', 'offline', 'unavailable', 'unsubscribe'],
        :next_scan.lt => DateTime.now).each do |user|
        TwitterSpy::UserInfo.new(@client).update(user)
      end
    end

    def run_loop
      puts "Processing at #{DateTime.now.to_s}..."
      update_status
      process_tracks
      process_user_specific
      $stdout.flush
      sleep TwitterSpy::Config::LOOP_SLEEP
      repository(:default).adapter.query(
        "delete from tracks where id not in (select track_id from user_tracks)"
      )
    rescue StandardError, Interrupt
      puts "Got exception:  #{$!.inspect}\n" + $!.backtrace.join("\n\t")
      $stdout.flush
      sleep 5
    end

  end

end
