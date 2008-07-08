require 'rubygems'
gem 'dm-core'
require 'dm-core'

module TwitterSpy
  module Config
    CONF = ::YAML.load_file 'twitterspy.yml'
    LOOP_SLEEP = CONF['general'].fetch('loop_sleep', 60).to_i
    WATCH_FREQ = CONF['general'].fetch('watch_freq', 10).to_i
    SCREEN_NAME = CONF['xmpp']['jid']

    DataMapper.setup(:default, CONF['general']['db'])
  end
end
