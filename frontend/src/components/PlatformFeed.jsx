import React, { useState, useEffect, useRef } from 'react';
import { getFeed, getAudio } from '../api';
import DailyDigest from './DailyDigest';
import './PlatformFeed.css';

function formatDate(dateStr) {
  if (!dateStr) return '';
  const d = new Date(dateStr);
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

export default function PlatformFeed() {
  const [feed, setFeed] = useState([]);
  const [loading, setLoading] = useState(true);
  const [playingId, setPlayingId] = useState(null);
  const audioRef = useRef(null);

  useEffect(() => {
    let cancelled = false;
    getFeed()
      .then((data) => { if (!cancelled) setFeed(data); })
      .catch(() => {})
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);

  function handlePlay(podcastId) {
    if (playingId === podcastId) {
      if (audioRef.current) audioRef.current.pause();
      setPlayingId(null);
    } else {
      setPlayingId(podcastId);
    }
  }

  return (
    <div className="platform-feed">
      <div className="feed-hero">
        <span className="feed-hero-badge">On Air</span>
        <h2 className="feed-hero-title">CineVox Podcast Feed</h2>
        <p className="feed-hero-sub">AI-powered film reviews, delivered fresh</p>
      </div>

      <DailyDigest />

      {loading && (
        <div className="feed-loading">Loading episodes...</div>
      )}

      {!loading && feed.length > 0 && (
        <>
          <div className="feed-section-label">
            <span className="feed-section-badge">Episodes</span>
            <span className="feed-section-text">Your Podcasts</span>
          </div>

          <div className="feed-grid">
        {feed.filter((ep) => ep.image_url).map((ep) => (
          <article key={ep.podcast_id} className="feed-card">
            {ep.image_url ? (
              <div className="feed-card-image-wrap">
                <img
                  className="feed-card-image"
                  src={ep.image_url}
                  alt={`Cover for ${ep.title}`}
                  loading="lazy"
                />
                <button
                  className={`feed-play-overlay ${playingId === ep.podcast_id ? 'playing' : ''}`}
                  onClick={() => handlePlay(ep.podcast_id)}
                  aria-label={playingId === ep.podcast_id ? 'Pause' : 'Play'}
                >
                  {playingId === ep.podcast_id ? (
                    <svg viewBox="0 0 24 24" width="32" height="32">
                      <rect x="6" y="4" width="4" height="16" fill="currentColor" />
                      <rect x="14" y="4" width="4" height="16" fill="currentColor" />
                    </svg>
                  ) : (
                    <svg viewBox="0 0 24 24" width="32" height="32">
                      <polygon points="6,3 20,12 6,21" fill="currentColor" />
                    </svg>
                  )}
                </button>
              </div>
            ) : (
              <div className="feed-card-no-image">
                <button
                  className="feed-play-btn-alt"
                  onClick={() => handlePlay(ep.podcast_id)}
                  aria-label="Play"
                >
                  <svg viewBox="0 0 24 24" width="28" height="28">
                    <polygon points="6,3 20,12 6,21" fill="currentColor" />
                  </svg>
                </button>
              </div>
            )}

            <div className="feed-card-body">
              {ep.tagline && <p className="feed-card-tagline">{ep.tagline}</p>}
              <h3 className="feed-card-title">{ep.title}</h3>
              {ep.date && <p className="feed-card-date">{formatDate(ep.date)}</p>}
              {ep.summary && <p className="feed-card-summary">{ep.summary}</p>}

              {ep.keywords && ep.keywords.length > 0 && (
                <div className="feed-card-keywords">
                  {ep.keywords.map((kw, i) => (
                    <span key={i} className="feed-keyword">#{kw}</span>
                  ))}
                </div>
              )}

              {ep.ratings && ep.ratings.length > 0 && (
                <div className="feed-card-ratings">
                  {ep.ratings.map((r) => (
                    <div key={r.title} className="feed-rating-row">
                      <span className="feed-rating-title">{r.title}</span>
                      <span className="feed-rating-scores">
                        {r.tmdb && <span className="feed-score tmdb">TMDB {r.tmdb}</span>}
                        {r.imdb && <span className="feed-score imdb">IMDb {r.imdb}</span>}
                        {r.rotten_tomatoes && <span className="feed-score rt">RT {r.rotten_tomatoes}</span>}
                      </span>
                    </div>
                  ))}
                </div>
              )}

              {ep.movies_covered && ep.movies_covered.length > 0 && (
                <div className="feed-card-movies">
                  {ep.movies_covered.map((m) => (
                    <span key={m} className="feed-movie-tag">{m}</span>
                  ))}
                </div>
              )}
            </div>

            <div className="feed-card-footer">
              <span className="feed-card-source">CineVox AI</span>
              <button
                className="feed-listen-btn"
                onClick={() => handlePlay(ep.podcast_id)}
              >
                {playingId === ep.podcast_id ? 'Pause' : 'Listen'}
              </button>
            </div>

            {playingId === ep.podcast_id && (
              <div className="feed-card-player">
                {/* eslint-disable-next-line jsx-a11y/media-has-caption */}
                <audio
                  ref={audioRef}
                  className="feed-audio"
                  controls
                  autoPlay
                  src={getAudio(ep.podcast_id)}
                  onEnded={() => setPlayingId(null)}
                />
              </div>
            )}
          </article>
        ))}
      </div>
        </>
      )}

      {!loading && feed.length === 0 && (
        <div className="feed-empty">
          <p className="feed-empty-title">No episodes yet</p>
          <p className="feed-empty-sub">Create your first podcast in the Studio</p>
        </div>
      )}
    </div>
  );
}
