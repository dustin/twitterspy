require 'memcache'

module TwitterSpy
  module DeliveryHelper
    def deliver(recipient, msg, dedupid=nil, type=:chat)
      unless(duplicate?(recipient, dedupid))
        if message.kind_of?(Jabber::Message)
          msg = message
          msg.to = jid
        else
          msg = Jabber::Message.new(jid)
          msg.type = type
          msg.body = message
        end
        @client.send msg
      end
    end

    def duplicate?(recipient, dedupid)
      if !dedupid.nil?
        key = "#{recipient}/#{dedupid}"
        if @cache.get(key)
          puts "Suppressing send of #{dedupid} to #{recipient}"
          $stdout.flush
          true
        else
          @cache.set key, '1', (20*60)
          false
        end
      end
    rescue
      puts "Error in duplicate checking code:  #{$!}" + $!.backtrace.join("\n\t")
      $stdout.flush
      false
    end
  end
end

