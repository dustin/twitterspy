require 'twitterspy/user_info'

module TwitterSpy

  class UserInfo

    include MsgFormatter
    include TwitterSpy::DeliveryHelper

    def initialize(client)
      @client = client
    end

    def update(user)
      TwitterSpy::Threading::TWIT_R_QUEUE << Proc.new do
        puts "Processing private stuff for #{user.jid} (@#{user.username})"
        $stdout.flush

        do_private_messages user
        do_friend_messages user unless user.friend_timeline_id.nil?
        user.update_attributes(
          :next_scan => (DateTime.now + Rational(TwitterSpy::Config::PERSONAL_FREQ, 1440)))
      end
    end

    private

    def do_friend_messages(user)
      twitter = twitter_conn user
      msgs = twitter.timeline.select{|m| m.id.to_i > user.friend_timeline_id}
      user.update_attributes(:friend_timeline_id => msgs.first.id.to_i) if msgs.size > 0
      deliver_messages(:friend, user, 'Friend Message', msgs)
    end

    def do_private_messages(user)
      first_time = user.direct_message_id.nil?
      twitter = twitter_conn user
      # TODO:  Fix the twitter API to let me pass in my direct message ID
      msgs = twitter.direct_messages.select{|m| m.id.to_i > user.direct_message_id.to_i}
      user.update_attributes(:direct_message_id => msgs.first.id.to_i) if msgs.size > 0
      deliver_messages(:private, user, 'Direct Message', msgs) unless first_time
    end

    def deliver_messages(type, user, subject, msgs)
      msgs.sort_by{|m| m.id.to_i}.each do |msg|
        from = msg.respond_to?(:sender_screen_name) ? msg.sender_screen_name : msg.user.screen_name
        deliver_message(type, user, subject, from, msg.text, msg.id.to_i)
      end
    end

    def deliver_message(type, user, subject, msgfrom, msgtext, msgid)
      deliver user.jid, format_msg(user.jid,
        msgfrom, msgtext, subject, type), msgid
    end

    def twitter_conn(user)
      password = Base64.decode64 user.password
      Twitter::Base.new user.username, password
    end
  end

end
