require 'rubygems'
require 'base64'

require 'twitter'

module TwitterSpy
  module Commands

    module CommandDefiner

      def all_cmds
        @@all_cmds ||= {}
      end

      def cmd(name, help, &block)
        all_cmds()[name.to_s] = help
        define_method(name, &block)
      end

    end

    class CommandProcessor

      extend CommandDefiner

      def initialize(conn)
        @jabber = conn
      end

      def typing_notification(user)
        @jabber.client.send("<message
            from='#{Config::SCREEN_NAME}'
            to='#{user.jid}'>
            <x xmlns='jabber:x:event'>
              <composing/>
            </x></message>")
      end

      def dispatch(cmd, user, arg)
        typing_notification user
        if self.respond_to? cmd
          self.send cmd.to_sym, user, arg
        else
          send_msg user, "I don't understand #{cmd}.  Send `help' for what I do know."
        end
      end

      def send_msg(user, text)
        @jabber.deliver user.jid, text
      end

      cmd :help, "Get help for commands." do |user, arg|
        cmds = self.class.all_cmds()
        help_text = cmds.keys.sort.map {|k| "#{k}\t#{cmds[k]}"}
        help_text << "\n"
        help_text << "The search is based on summize.  For options, see http://summize.com/operators"
        help_text << "Email questions, suggestions or complaints to dustin@spy.net"
        send_msg user, help_text.join("\n")
      end

      cmd :on, "Activate updates." do |user, nothing|
        change_user_active_state(user, true)
        send_msg user, "Marked you active."
      end

      cmd :off, "Disable updates." do |user, nothing|
        change_user_active_state(user, false)
        send_msg user, "Marked you inactive."
      end

      cmd :track, "Track a topic (summize query string)" do |user, arg|
        with_arg(user, arg) do |a|
          user.track a
          send_msg user, "Tracking #{a}"
        end
      end

      cmd :untrack, "Stop tracking a topic" do |user, arg|
        with_arg(user, arg) do |a|
          user.untrack a
          send_msg user, "Stopped tracking #{a}"
        end
      end

      cmd :tracks, "List your tracks." do |user, arg|
        tracks = user.tracks.map{|t| t.query}.sort
        send_msg user, "Tracking #{tracks.size} topics\n" + tracks.join("\n")
      end

      cmd :search, "Perform a sample search (but do not track)" do |user, arg|
        with_arg(user, arg) do |query|
          summize_client = Summize::Client.new 'twitterspy@jabber.org'
          res = summize_client.query query, :rpp => 2
          out = ["Results from your query:"]
          res.each do |r|
            out << "#{r.from_user}: #{r.text}"
          end
          send_msg user, out.join("\n")
        end
      end

      cmd :twlogin, "Set your twitter username and password (use at your own risk)" do |user, arg|
        with_arg(user, arg, "You must supply a username and password") do |up|
          u, p = up.strip.split(/\s+/, 2)
          TwitterSpy::Threading::IN_QUEUE << Proc.new do
            twitter = Twitter::Base.new u, p
            begin
              twitter.verify_credentials
              user.update_attributes(:username => u, :password => Base64.encode64(p).strip)
              send_msg user, "Your credentials have been verified and saved.  Thanks."
            rescue StandardError, Interrupt
              puts "Unable to verify credentials:  #{$!}\n" + $!.backtrace.join("\n\t")
              $stdout.flush
              send_msg user, "Unable to verify your credentials.  They're either wrong or twitter is broken."
            end
          end
        end
      end

      cmd :post, "Post a message to twitter." do |user, arg|
        twitter_call user, arg, "You need to actually tell me what to post" do |message|
          begin
            password = Base64.decode64 user.password
            twitter = Twitter::Base.new user.username, password
            rv = twitter.post message
            url = "http://twitter.com/#{user.username}/statuses/#{rv.id}"
            send_msg user, ":) Your message has been posted to twitter: " + url
          rescue StandardError, Interrupt
            puts "Failed to post to twitter:  #{$!}\n" + $!.backtrace.join("\n\t")
            $stdout.flush
            send_msg user, ":( Failed to post your message.  Your password may be wrong, or twitter may be broken."
          end
        end
      end

      cmd :lang, "Set your language (either 2 letter ISO code or empty for any)" do |user, arg|
        arg = nil if arg && arg.strip == ""
        if arg && arg.size != 2
          send_msg user, "Language should be a 2-digit country code."
          return
        end

        user.update_attributes(:language => arg)
        if arg
          send_msg user, "Set your language to #{arg}"
        else
          send_msg user, "Unset your language."
        end
      end

      private

      def twitter_call(user, arg, missing_text="Argument needed.", &block)
        if not_valid(user.username) || not_valid(user.password)
          send_msg user, "I don't know your username or password.  Use twlogin to set creds."
          return
        end

        password = Base64.decode64 user.password

        with_arg(user, arg, missing_text) do |a|
          TwitterSpy::Threading::IN_QUEUE << Proc.new do
            yield a
          end
        end
      end

      def not_valid(s)
        s.nil? || s == ''
      end

      def with_arg(user, arg, missing_text="Please supply a summize query")
        if arg.nil? || arg.strip == ""
          send_msg user, missing_text
        else
          yield arg.strip
        end
      end

      def change_user_active_state(user, to)
        if user.active != to
          user.active = to
          user.availability_changed
          user.save
        end
      end

    end # CommandProcessor

  end
end
