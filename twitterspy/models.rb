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
  # min_id holds the minimum ID of any tweet to be delivered to this user.
  # This is an additional constraint over the track-specific max_seen ID.
  property :min_id, Integer, :nullable => false, :default => 0
  property :language, String, :length => 2
  property :auto_post, Boolean, :nullable => false, :default => false

  has n, :user_tracks
  has n, :tracks, :through => :user_tracks

  # Find or create a user and update the status
  def self.update_status(jid, status)
    u = first(:jid => jid) || create!(:jid => jid)
    was_available = u.available?
    u.status = status
    u.availability_changed unless u.available? == was_available
    u.save
    u
  end

  # Callback for when the availability state of a user has changed.
  # Note:  This is called on an *unsaved* object that will soon be saved.
  def availability_changed
    if available?
      self.min_id = user_tracks.map{|t| t.track.max_seen}.max.to_i + 1
      puts "#{self.jid} has just become available.  Set min_id to #{self.min_id}"
    end
  rescue
    puts "Error updating #{self.jid} for an availability change:  #{$!}" +
      $!.backtrace.join("\n\t")
    $stdout.flush
  end

  def track(query)
    t = Track.first(:query => query) || Track.create(:query => query, :next_update => DateTime.now)
    user_tracks.first(:track_id => t.id) || user_tracks.create(:track => t, :user => self)
  end

  def untrack(query)
    t = Track.first(:query => query) or return false
    ut = user_tracks.first(:track_id => t.id) or return false
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
  property :next_update, DateTime, :nullable => false
  property :max_seen, Integer

  has n, :user_tracks
  has n, :users, :through => :user_tracks

  def self.todo
    q=<<EOF
    select distinct t.id
      from tracks t
      join user_tracks ut on (t.id = ut.track_id)
      join users u on (u.id == ut.user_id)
      where
        u.active is not null
        and u.active = ?
        and u.status not in ('dnd', 'offline', 'unavailable')
        and ( t.next_update < ? )
      order by t.last_update
      limit 60
EOF
    ids = repository(:default).adapter.query(q, true, DateTime.now)
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
