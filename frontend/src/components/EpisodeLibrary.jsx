import React, { useState, useEffect } from 'react';
import { getEpisodes } from '../api';
import './EpisodeLibrary.css';

function formatDate(dateStr) {
  const d = new Date(dateStr);
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

export default function EpisodeLibrary({ onSelectEpisode }) {
  const [episodes, setEpisodes] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    getEpisodes()
      .then((data) => { if (!cancelled) setEpisodes(data); })
      .catch(() => {})
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);

  if (loading) {
    return <div className="episode-library"><p className="library-loading">Loading episodes...</p></div>;
  }

  if (episodes.length === 0) {
    return null;
  }

  return (
    <div className="episode-library">
      <div className="library-header">
        <span className="library-badge">Archive</span>
        <h3 className="library-title">Past Episodes</h3>
      </div>
      <div className="episode-list">
        {episodes.map((ep) => (
          <button
            key={ep.episode_id}
            className="episode-row"
            onClick={() => onSelectEpisode(ep)}
            disabled={!ep.has_audio}
          >
            <div className="episode-row-left">
              <span className="episode-row-title">{ep.title}</span>
              <span className="episode-row-meta">
                {formatDate(ep.date)}
                {ep.movies_covered && ep.movies_covered.length > 0 &&
                  ` / ${ep.movies_covered.join(', ')}`}
              </span>
            </div>
            <div className="episode-row-right">
              {ep.has_audio ? (
                <span className="episode-play-icon" aria-label="Play">
                  <svg viewBox="0 0 24 24" width="16" height="16">
                    <polygon points="6,3 20,12 6,21" fill="currentColor" />
                  </svg>
                </span>
              ) : (
                <span className="episode-unavailable">unavailable</span>
              )}
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
