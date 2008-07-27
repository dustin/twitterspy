require 'twitterspy/msg_formatter'

module TwitterSpy

  class Tracker

    include TwitterSpy::MsgFormatter
    include TwitterSpy::DeliveryHelper

    def initialize(client)
      @client=client
    end

    def update
      outbound=Hash.new { |h,k| h[k] = {}; h[k] }
      Track.todo.each do |track|
        puts "Fetching #{track.query} at #{Time.now.to_s}"
        summize_client = Summize::Client.new TwitterSpy::Config::USER_AGENT
        begin
          oldid = track.max_seen.to_i
          res = summize_client.query track.query, :since_id => oldid
          track.update_attributes(:last_update => DateTime.now,
            :max_seen => res.max_id,
            :next_update => compute_next_update(track))
          totx = oldid == 0 ? Array(res).last(5) : res.select { |x| x.id.to_i > oldid }
          track.users.select{|u| u.available? }.each do |user|
            totx.each do |msg|
              if user.language.nil? || msg.language.nil? || user.language == msg.language
                outbound[user.jid][msg.id] = msg if msg.id.to_i > user.min_id
              end
            end
          end
        rescue StandardError, Interrupt
          puts "Error fetching #{track.query}: #{$!}" + $!.backtrace.join("\n\t")
        end
      end
      outbound.each do |jid, msgs|
        puts "Sending #{msgs.size} messages to #{jid}"
        msgs.keys.sort.each do |msgk|
          msg = msgs[msgk]
          send_track_message jid, msg
        end
      end
      $stdout.flush
    end

    def send_track_message(jid, msg)
      deliver jid, format_msg(jid, msg.from_user, msg.text, "Track Message"), msg.id.to_i
    end

    def compute_next_update(track)
      # Give preference to common tracks.
      # Find the active user count for this track
      # XXX:  Getting a copy of the track to work around a DM bug.
      track = track.clone
      count = track.users(:active => true,
        :status.not => ['dnd', 'offline', 'unavailable', 'unsubscribe']).size
      mins = [TwitterSpy::Config::WATCH_FREQ,
        TwitterSpy::Config::WATCH_FREQ - (count - 1)].min
      # But keep it above 0.
      mins = 1 if mins < 1
      if mins < TwitterSpy::Config::WATCH_FREQ
        puts "Reduced track freq for #{track.query} to #{mins} for #{count} active watchers"
      end
      DateTime.now + Rational(mins, 1440)
    end

  end

end
