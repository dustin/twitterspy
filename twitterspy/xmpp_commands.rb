require 'rubygems'
require 'base64'

require 'twitterspy/models'

module TwitterSpy

  module XMPPCommands

    class Base
      attr_reader :node, :name, :description

      def initialize(node, name, description)
        @node=node
        @name=name
        @description=description
      end

      def execute(conn, user, iq)
        raise "Not Implemented"
      end

      def send_result(conn, iq, status=:completed, &block)
        cmd_node = iq.command.attributes['node']
        i = Jabber::Iq::new(:result, iq.from)
        i.from = TwitterSpy::Config::SCREEN_NAME
        i.id = iq.id
        com = i.add_element(Jabber::Command::IqCommand::new(cmd_node))
        com.status = status
        yield com if block_given?
        conn.send i
      end

      def get_twitter(user)
        password = Base64.decode64 user.password
        Twitter::Base.new user.username, password
      end

    end

    class MultiBase < Base

      def next_actions(com, execute, *actions)
        ael = com.add_element("actions")
        ael.attributes['execute'] = execute
        actions.each {|a| ael.add_element a}
      end

      def add_field(form, name, label, value=nil, type=:text_single)
        ufield = form.add_element(Jabber::Dataforms::XDataField.new(name, type))
        ufield.label = label
        ufield.value = value.to_s unless value.nil?
        ufield
      end

      def execute(conn, user, iq)
        case iq.command.action
        when :cancel
          send_result(conn, iq, :canceled)
        when nil, :complete
          args = iq.command.first_element('x')
          if args.blank?
            send_result(conn, iq, :executing) do |com|
              add_form(user, iq, com)
            end
          else
            complete(conn, user, iq, args)
          end
        end
      rescue
        puts "Error executing command (#{@node}): #{$!}" + $!.backtrace.join("\n\t")
        $stdout.flush
        send_result(conn, iq) do |com|
          note = com.add_element('note')
          note.attributes['type'] = 'error'
          note.add_text($!.to_s)
          error = com.add_element(Jabber::ErrorResponse.new('bad-request'))
        end
      end

    end

    class Version < Base

      def initialize
        super('version', 'Version', 'Get the current version of the bot software.')
      end

      def execute(conn, user, iq)
        puts "Executing version..."
        send_result(conn, iq) do |com|
          form = com.add_element(Jabber::Dataforms::XData::new('result'))
          v = form.add_element(Jabber::Dataforms::XDataField.new('version', 'text-single'))
          v.value = TwitterSpy::Config::VERSION
        end
      end

    end

    class UnTrack < MultiBase

      def initialize
        super('untrack', 'Remove a Track', 'Remove a track query.')
      end

      def add_form(user, iq, com)
        next_actions(com, 'execute', 'complete')

        form = com.add_element(Jabber::Dataforms::XData.new)
        form.title = 'Untrack one or more current tracks.'
        form.instructions = "Select the queries to stop tracking and submit."

        f=add_field(form, 'torm', 'Tracks', nil, :list_multi)
        f.options = user.tracks.sort_by{|t| t.query}.map{|t| [t.id, t.query]}
      end

      def complete(conn, user, iq, args)
        torm = args.fields.select {|f| f.var == 'torm'}.first
        torm.values.each do |i|
          puts "Untracking #{i}"
          user.untrack i.to_i
        end
        send_result(conn, iq)
      end

    end

    class TWLogin < MultiBase
      def initialize
        super('twlogin', 'Login to Twitter', 'Set twitter credentials.')
      end

      def add_form(user, iq, com)
        next_actions com, 'execute', 'complete'

        form = com.add_element(Jabber::Dataforms::XData.new)
        form.title = "Login to Twitter"
        form.instructions = 'Logging into twitter allows posting, following, and other such commands to work.'

        add_field form, 'login', 'Username'
        add_field form, 'password', 'Password', nil, :text_private
      end

      def complete(conn, user, iq, args)
        h=Hash[*args.fields.map {|f| [f.var, f.value]}.flatten]
        u=h['login']
        p=h['password']
        TwitterSpy::Threading::TWIT_W_QUEUE << Proc.new do
          twitter = Twitter::Base.new u, p
          begin
            twitter.verify_credentials
            user.update_attributes(:username => u, :password => Base64.encode64(p).strip, :next_scan => DateTime.now)
            send_result conn, iq
          rescue StandardError, Interrupt
            puts "Unable to verify credentials:  #{$!}\n" + $!.backtrace.join("\n\t")
            $stdout.flush
            send_result(conn, iq) do |com|
              note = com.add_element('note')
              note.attributes['type'] = 'error'
              note.add_text('Unable to verify your credentials.')
              error = com.add_element(Jabber::ErrorResponse.new('bad-request'))
            end
          end
        end
      end
    end

    class Preferences < MultiBase
      def initialize
        super("preferences", "Set Preferences", "Set various TwitterSpy preferences.")
      end

      def add_form(user, iq, com)
        next_actions com, 'execute', 'complete'

        form = com.add_element(Jabber::Dataforms::XData.new)
        form.title = "Set TwitterSpy Preferences"
        form.instructions = 'Set various basic twitterspy preferences.'

        add_field form, 'autopost', 'Autopost', user.auto_post, :boolean
        add_field form, 'watch_friends', 'Watch friends', !user.friend_timeline_id.nil?, :boolean
        add_field form, 'language', 'Language (e.g. en)', user.language
      end

      def complete(conn, user, iq, args)
        h=Hash[*args.fields.map {|f| [f.var, f.value]}.flatten]
        user.auto_post = h['autopost'] == '1'
        user.language = h['language']

        # this processes asynchronously.
        if h['watch_friends'] == '1' && user.logged_in?
          puts "...Enabling friend watching"
          twitter = get_twitter user
          TwitterSpy::Threading::TWIT_W_QUEUE << Proc.new do
            begin
              item = twitter.timeline.first
              user.friend_timeline_id = item.id.to_i
              user.save
              send_result conn, iq
            rescue
              puts "Failed to do initial friend stuff lookup for user: #{$!}\n" + $!.backtrace.join("\n\t")
              $stdout.flush
              send_result(conn, iq) do |com|
                note = com.add_element('note')
                note.attributes['type'] = 'error'
                note.add_text('error getting initial friend list: ' + $!.to_s)
                error = com.add_element(Jabber::ErrorResponse.new('bad-request'))
              end
            end
          end
        else
          puts "... disabling friend watching."
          user.friend_timeline_id = nil
          user.save
          send_result conn, iq
        end
      end
    end

    def self.commands
      constants.map{|c| const_get c}.select {|c| c != Base && c != MultiBase }
    end
  end

end