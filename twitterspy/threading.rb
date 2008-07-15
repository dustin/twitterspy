require 'thread'

module TwitterSpy
  module Threading
    IN_QUEUE = Queue.new
    TWIT_QUEUE = Queue.new

    def self.start_worker(queue)
      Thread.new do
        loop do
          begin
            msg = queue.pop
            msg.call
          rescue StandardError, Interrupt
            puts "ERROR!  #{$!}\n#{$!.backtrace.join("\n\t")}"
            $stdout.flush
          rescue
            puts "ERROR!  #{$!}\n#{$!.backtrace.join("\n\t")}"
            $stdout.flush
          end
        end
      end
    end

  end
end
