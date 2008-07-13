require 'twitterspy/tracker'

module TwitterSpy

  class Main

    def server=(server)
      @server = server
    end

    def process_xmpp_incoming
      rv = 0
      @server.presence_updates do |user, status, message|
        User.update_status user, status
        rv += 1
      end
      # Called for dequeue side-effect stupidity of jabber:simple
      rv += @server.received_messages.size
      @server.new_subscriptions do |from, presence|
        puts "Subscribed by #{from}"
        rv += 1
      end
      @server.subscription_requests do |from, presence|
        puts "Sub req from #{from}"
        rv += 1
      end
      rv
    end

    def process_message(msg)
      decoded = HTMLEntities.new.decode(msg.body).gsub(/&/, '&amp;')
      cmd, args = decoded.split(' ', 2)
      cp = TwitterSpy::Commands::CommandProcessor.new @server
      user = User.first(:jid => msg.from.bare.to_s) || User.create(:jid => msg.from.bare.to_s)
      cp.dispatch cmd.downcase, user, args
    end

    def update_status
      users = User.count
      tracks = Track.count
      puts "Updating status with #{users} users and #{tracks} tracks"
      status = "Tracking #{tracks} topics for #{users} users"
      @server.send!(Jabber::Presence.new(nil, status,
        TwitterSpy::Config::CONF['xmpp'].fetch('priority', 1).to_i))
    end

    def process_tracks
      TwitterSpy::Threading::IN_QUEUE << Proc.new do
        TwitterSpy::Tracker.new(@server).update
      end
    end

    def run_loop
      puts "Processing at #{DateTime.now.to_s}..."
      process_xmpp_incoming
      update_status
      process_tracks
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

  end

end
