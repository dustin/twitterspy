require 'rubygems'
gem 'dm-core'
require 'dm-core'
require 'dm-aggregates'

class User
  include DataMapper::Resource
  property :id, Integer, :serial => true
  property :jid, String, :nullable => false, :length => 128
  property :username, String
  property :password, String
  property :active, Boolean, :nullable => false, :default => true
  property :status, String

  # Find or create a user and update the status
  def self.update_status(jid, status)
    u = first(:jid => jid) || create!(:jid => jid)
    u.status = status
    u.save
    u
  end
end
