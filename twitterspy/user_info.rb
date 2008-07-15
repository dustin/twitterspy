module TwitterSpy

  class UserInfo

    def initialize(server)
      @server = server
    end

    def update(user)
      TwitterSpy::Threading::IN_QUEUE << Proc.new do
        first_time = user.direct_message_id.nil?
        twitter = twitter_conn user
        # TODO:  Fix the twitter API to let me pass in my direct message ID
        msgs = twitter.direct_messages.select{|m| m.id.to_i > user.direct_message_id}
        user.update_attributes(:direct_message_id => msgs.first.id.to_i) if msgs.size > 0
        deliver_messages(:private, user, msgs) unless first_time
      end
    end

    private

    def deliver_messages(type, user, msgs)
      msgs.each do |msg|
        deliver_message(type, user, msg)
      end
    end

    def deliver_message(type, user, msg)
      @server.deliver user.jid, "#{type} message from @#{msg.sender_screen_name}: #{msg.text}"
    end

    def twitter_conn(user)
      password = Base64.decode64 user.password
      Twitter::Base.new user.username, password
    end
  end

end