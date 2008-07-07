require 'rubygems'
gem 'dm-core'
require 'dm-core'
require 'dm-aggregates'

class User
  include DataMapper::Resource
  property :id, Integer, :serial => true, :unique_index => true
  property :jid, String, :nullable => false, :length => 128, :unique_index => true
  property :username, String
  property :password, String
  property :active, Boolean, :nullable => false, :default => true
  property :status, String

  has n, :user_tracks
  has n, :tracks, :through => :user_tracks

  # Find or create a user and update the status
  def self.update_status(jid, status)
    u = first(:jid => jid) || create!(:jid => jid)
    u.status = status
    u.save
    u
  end

  def track(query)
    t = Track.first(:query => query) || Track.create(:query => query)
    user_tracks.first(:track_id => t.id) || user_tracks.create(:track => t, :user => self)
  end

  def untrack(query)
    t = Track.first(:query => query) or return
    ut = user_tracks.first(:track_id => t.id) or return
    ut.destroy
  end

  def available?
    self.active && !['offline', 'dnd', 'unavailable'].include?(self.status)
  end
end

class Track
  include DataMapper::Resource
  property :id, Integer, :serial => true, :unique_index => true
  property :query, String, :nullable => false, :unique_index => true
  property :last_update, DateTime
  property :max_seen, Integer

  has n, :user_tracks
  has n, :users, :through => :user_tracks

  def self.todo(timeout=10)
    q=<<EOF
    select distinct t.id
      from tracks t
      join user_tracks ut on (t.id = ut.track_id)
      join users u on (u.id == ut.user_id)
      where
        u.active is not null
        and u.active = ?
        and u.status not in ('dnd', 'offline', 'unavailable')
        and ( t.last_update is null or t.last_update < ?)
      limit 50
EOF
    ids = repository(:default).adapter.query(q, true,
      DateTime.now - Rational(timeout, 1440))
    self.all(:conditions => {:id => ids})
  end
end

class UserTrack
  include DataMapper::Resource
  property :id, Integer, :serial => true, :unique_index => true
  property :user_id, Integer, :nullable => false, :unique_index => :idx_ut_ut
  property :track_id, Integer, :nullable => false, :unique_index => :idx_ut_ut
  property :created_at, DateTime
  belongs_to :user
  belongs_to :track
end
