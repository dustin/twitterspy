require 'rubygems'
require 'base64'

require 'twitter'

module TwitterSpy
  module Commands

    class Help
      attr_accessor :short_help, :full_help

      def initialize(short_help)
        @short_help = @full_help = short_help
      end

      def to_s
        @short_help
      end
    end

    module CommandDefiner

      def all_cmds
        @@all_cmds ||= {}
      end

      def cmd(name, help, &block)
        all_cmds()[name.to_s] = TwitterSpy::Commands::Help.new help
        define_method(name, &block)
      end

      def help_text(name, text)
        all_cmds()[name.to_s].full_help = text
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
        if arg.blank?
          out = ["Available commands:"]
          out << "Type `help somecmd' for more help on `somecmd'"
          out << ""
          out << cmds.keys.sort.map{|k| "#{k}\t#{cmds[k]}"}
          out << ""
          out << "The search is based on summize.  For options, see http://summize.com/operators"
          out << "Email questions, suggestions or complaints to dustin@spy.net"
          send_msg user, out.join("\n")
        else
          h = cmds[arg]
          if h
            out = ["Help for `#{arg}'"]
            out << h.full_help
            send_msg user, out.join("\n")
          else
            send_msg user, "Topic #{arg} is unknown.  Type `help' for known commands."
          end
        end
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
      help_text :track, <<-EOF
Track gives you all of the power of summize queries periodically delivered to your IM client.
Example queries:

track iphone
track iphone OR android
track iphone android

See http://summize.com/operators for details on what all you can do.
EOF

      cmd :untrack, "Stop tracking a topic" do |user, arg|
        with_arg(user, arg) do |a|
          user.untrack a
          send_msg user, "Stopped tracking #{a}"
        end
      end
      help_text :untrack, <<-EOF
Untrack tells twitterspy to stop tracking the given query.
Examples:

untrack iphone
untrack iphone OR android
untrack iphone android
EOF

      cmd :tracks, "List your tracks." do |user, arg|
        tracks = user.tracks.map{|t| t.query}.sort
        send_msg user, "Tracking #{tracks.size} topics\n" + tracks.join("\n")
      end

      cmd :search, "Perform a sample search (but do not track)" do |user, arg|
        with_arg(user, arg) do |query|
          TwitterSpy::Threading::IN_QUEUE << Proc.new do
            summize_client = Summize::Client.new 'twitterspy@jabber.org'
            res = summize_client.query query, :rpp => 2
            out = ["Results from your query:"]
            res.each do |r|
              out << "#{r.from_user}: #{r.text}"
            end
            send_msg user, out.join("\n\n")
          end
        end
      end

      cmd :whois, "Find out who a particular user is." do |user, arg|
        twitter_call user, arg, "For whom are you looking?" do |twitter, username|
          begin
            u = twitter.user username.strip
            out = ["#{username} is #{u.name.blank? ? 'Someone' : u.name} from #{u.location.blank? ? 'Somewhere' : u.location}"]
            out << "Most recent tweets:"
            summize_client = Summize::Client.new 'twitterspy@jabber.org'
            res = summize_client.query "from:#{username.strip}", :rpp => 3
            # Get the first status from the twitter response (in case none is indexed)
            out << "\n1) #{u.status.text}"
            res.each_with_index do |r, i|
              out << "\n#{i+1}) #{r.text}" if i > 0
            end
            out << "\nhttp://twitter.com/#{username.strip}"
            send_msg user, out.join("\n")
          rescue StandardError, Interrupt
            puts "Unable to do a whois:  #{$!}\n" + $!.backtrace.join("\n\t")
            $stdout.flush
            send_msg user, "Unable to get information for #{username}"
          end
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
      help_text :twlogin, <<-EOF
Provide login credentials for twitter.
NOTE: Giving out your credentials is dangerous.  We will try to keep them safe, but we can't make any promises.
Example usage:

twlogin mytwittername myr4a11yk0mp13xp455w0rd
EOF

      cmd :twlogout, "Discard your twitter credentials" do |user, arg|
        user.update_attributes(:username => nil, :password => nil)
        send_msg user, "You have been logged out."
      end

      cmd :status, "Find out what you look like to us." do |user, arg|
        out = ["Jid:  #{user.jid}"]
        out << "Jabber Status:  #{user.status}"
        out << "TwitterSpy state:  #{user.active ? 'Active' : 'Not Active'}"
        if logged_in?(user)
          out << "Logged in for twitter API services as #{user.username}"
        else
          out << "You're not logged in for twitter API services."
        end
        out << "You are currently tracking #{user.tracks.size} topics."
        send_msg user, out.join("\n")
      end

      cmd :post, "Post a message to twitter." do |user, arg|
        twitter_call user, arg, "You need to actually tell me what to post" do |twitter, message|
          begin
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

      cmd :follow, "Follow a user" do |user, arg|
        twitter_call user, arg, "Whom would you like to follow?" do |twitter, username|
          begin
            twitter.follow username
            send_msg user, ":) Now following #{username}"
          rescue StandardError, Interrupt
            puts "Failed to follow a user:  #{$!}\n" + $!.backtrace.join("\n\t")
            $stdout.flush
            send_msg user, ":( Failed to follow #{username} #{$!}"
          end
        end
      end

      cmd :leave, "Leave (stop following) a user" do |user, arg|
        twitter_call user, arg, "Whom would you like to leave?" do |twitter, username|
          begin
            twitter.leave username
            send_msg user, ":) No longer following #{username}"
          rescue StandardError, Interrupt
            puts "Failed to stop following a user:  #{$!}\n" + $!.backtrace.join("\n\t")
            $stdout.flush
            send_msg user, ":( Failed to leave #{username} #{$!}"
          end
        end
      end

      cmd :lang, "Set your language." do |user, arg|
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
      help_text :lang, <<-EOF
Set or clear your language preference.
With no argument, your language preference is cleared and you can receive tweets in any language.
Otherwise, supply a 2 letter ISO country code to restrict tracks to your favorite language.

Example: to set your language to English so only English tweets are returned from tracks:

lang en

Example: to unset your language:

lang
EOF

      private

      def logged_in?(user)
        !(user.username.blank? || user.password.blank?)
      end

      def twitter_call(user, arg, missing_text="Argument needed.", &block)
        if !logged_in?(user)
          send_msg user, "I don't know your username or password.  Use twlogin to set creds."
          return
        end

        password = Base64.decode64 user.password

        with_arg(user, arg, missing_text) do |a|
          TwitterSpy::Threading::IN_QUEUE << Proc.new do
            password = Base64.decode64 user.password
            twitter = Twitter::Base.new user.username, password
            yield twitter, a
          end
        end
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
