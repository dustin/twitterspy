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

    def user_link(user)
      linktext=user
      if user[0] == 64 # Does it start with @?
        user = user.gsub(/^@(.*)/, '\1')
      end
      %Q{<a href="http://twitter.com/#{user}">#{linktext}</a>}
    end

    def format_body(text)
      text.gsub(/(\W*)(@[\w_]+)/) {|x| $1 + user_link($2)}.gsub(/&/, '&amp;')
    end

    def send_track_message(jid, msg)
      body = "#{msg.from_user}: #{msg.text}"
      m = Jabber::Message::new(jid, body).set_type(:normal).set_id('1').set_subject("Track Message")

      # The html itself
      html = "#{user_link(msg.from_user)}: #{format_body(msg.text)}"
      begin
        REXML::Document.new "<html>#{html}</html>"

        h = REXML::Element::new("html")
        h.add_namespace('http://jabber.org/protocol/xhtml-im')

        # The body part with the correct namespace
        b = REXML::Element::new("body")
        b.add_namespace('http://www.w3.org/1999/xhtml')

        t = REXML::Text.new("#{user_link(msg.from_user)}: #{format_body(msg.text)}",
          false, nil, true, nil, %r/.^/ )

        b.add t
        h.add b
        m.add_element(h)
      rescue REXML::ParseException
        puts "Nearly made bad html:  #{$!} (#{html})"
        $stdout.flush
      end

      @server.deliver jid, m
    end

    def process_tracks
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
            send_track_message jid, msg
          end
        end
      end
    end

    def run_loop
      puts "Processing..."
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