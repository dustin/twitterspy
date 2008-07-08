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
        if arg.nil? || arg.strip == ""
          send_msg user, "Please supply a summize query."
        else
          user.track arg.strip
          send_msg user, "Tracking #{arg}"
        end
      end

      cmd :untrack, "Stop tracking a topic" do |user, arg|
        if arg.nil? || arg.strip == ""
          send_msg user, "Please supply a summize query."
        else
          user.untrack arg.strip
          send_msg user, "Stopped tracking #{arg}"
        end
      end

      cmd :tracks, "List your tracks." do |user, arg|
        tracks = user.tracks.map{|t| t.query}.sort
        send_msg user, "Tracking #{tracks.size} topics\n" + tracks.join("\n")
      end

      private

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
