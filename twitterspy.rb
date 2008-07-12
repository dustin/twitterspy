#!/usr/bin/env ruby

require 'rubygems'
require 'sqlite3'
require 'date'
require 'xmpp4r-simple'
require 'summize'
require 'htmlentities'

require 'twitterspy/config'
require 'twitterspy/models'
require 'twitterspy/commands'
require 'twitterspy/threading'
require 'twitterspy/main'

def inner_loop(main)
  loop do
    main.run_loop
  end
end

TwitterSpy::Config::CONF['general'].fetch('nthreads', 1).to_i.times do |t|
  puts "Starting thread #{t}"
  TwitterSpy::Threading.start_worker
end

class MyClient < Jabber::Simple

  def initialize(jid, pass, main)
    super(jid, pass)
    @main = main
    setup_callback
  end

  def reconnect
    puts "Reconnecting"
    $stdout.flush
    super
    setup_callback
  end

  def setup_callback
    @main.server = self
    client.add_message_callback do |message|
      begin
        @main.process_message message unless message.body.nil?
      rescue StandardError, Interrupt
        puts "Incoming message error:  #{$!}\n" + $!.backtrace.join("\n\t")
        $stdout.flush
        deliver message.from, "Error processing your message:  #{$!}"
      end
    end
  end

end

loop do
  puts "Connecting..."
  $stdout.flush
  # Jabber::debug=true
  main = TwitterSpy::Main.new
  server = MyClient.new(
    TwitterSpy::Config::CONF['xmpp']['jid'],
    TwitterSpy::Config::CONF['xmpp']['pass'],
    main)
  main.update_status

  puts "Set up with #{server.inspect}"
  $stdout.flush
  inner_loop main
end
