import React, { useState, useEffect } from 'react';
import { getAudio, createPost, getPostData } from '../api';
import './PodcastPlayer.css';

export default function PodcastPlayer({ podcastId, metadata = {}, onNewPodcast }) {
  const audioUrl = getAudio(podcastId);
  const { title, movies_covered, stage_timings } = metadata;
  const [postData, setPostData] = useState(null);
  const [posting, setPosting] = useState(false);
  const [postError, setPostError] = useState(null);
  const [loadingPost, setLoadingPost] = useState(true);

  const totalTime = stage_timings
    ? Object.values(stage_timings).reduce((a, b) => a + b, 0)
    : null;

  // Auto-fetch post data on mount
  useEffect(() => {
    let cancelled = false;
    async function fetchPost() {
      try {
        const data = await getPostData(podcastId);
        if (!cancelled) setPostData(data);
      } catch {
        // No pre-generated post data — that's fine
      } finally {
        if (!cancelled) setLoadingPost(false);
      }
    }
    fetchPost();
    return () => { cancelled = true; };
  }, [podcastId]);

  async function handleCreatePost() {
    setPosting(true);
    setPostError(null);
    try {
      const data = await createPost(podcastId);
      setPostData(data);
    } catch (err) {
      setPostError(err.message || 'Failed to create post');
    } finally {
      setPosting(false);
    }
  }

  return (
    <div className="podcast-player">
      <div className="player-banner">
        <span className="player-banner-label">Broadcast Ready</span>
        <span className="player-banner-id">{podcastId}</span>
      </div>

      <div className="player-info">
        <p className="player-show-name">CineVox</p>
        <h2 className="player-title">{title || `Episode ${podcastId}`}</h2>
        <p className="player-meta">
          AI-generated film review
          {totalTime ? ` / produced in ${Math.round(totalTime)}s` : ''}
        </p>
        {movies_covered && movies_covered.length > 0 && (
          <div className="movie-tags">
            {movies_covered.map((movie) => (
              <span key={movie} className="movie-tag">{movie}</span>
            ))}
          </div>
        )}
      </div>

      <div className="player-controls">
        {/* eslint-disable-next-line jsx-a11y/media-has-caption */}
        <audio className="audio-element" controls src={audioUrl} preload="metadata">
          Your browser does not support the audio element.
        </audio>

        <div className="player-actions">
          {!postData && !loadingPost && (
            <button
              className="post-btn"
              onClick={handleCreatePost}
              disabled={posting}
            >
              {posting ? (
                <><span className="spinner" aria-hidden="true" />Generating Post...</>
              ) : 'Create Post'}
            </button>
          )}
          <button className="new-episode-btn" onClick={onNewPodcast}>
            New Episode
          </button>
        </div>
        {postError && <p className="post-error">{postError}</p>}
      </div>

      {/* Post Card — shown automatically */}
      {loadingPost && (
        <div className="post-loading">
          <span className="spinner" aria-hidden="true" />
          <span>Loading post data...</span>
        </div>
      )}

      {postData && (
        <div className="post-card">
          <div className="post-card-header">
            <span className="post-card-badge">CineVox Post</span>
          </div>

          {postData.image_url && (
            <div className="post-card-image-wrap">
              <img
                className="post-card-image"
                src={postData.image_url}
                alt={`Cover art for ${postData.title}`}
              />
            </div>
          )}

          <div className="post-card-body">
            {postData.tagline && (
              <p className="post-card-tagline">{postData.tagline}</p>
            )}

            <h3 className="post-card-title">{postData.title}</h3>

            {postData.summary && (
              <p className="post-card-summary">{postData.summary}</p>
            )}

            {postData.keywords && postData.keywords.length > 0 && (
              <div className="post-card-keywords">
                {postData.keywords.map((kw, i) => (
                  <span key={i} className="post-keyword">#{kw}</span>
                ))}
              </div>
            )}

            {postData.ratings && postData.ratings.length > 0 && (
              <div className="post-card-ratings">
                <p className="post-card-ratings-label">Scores & Ratings</p>
                {postData.ratings.map((r) => (
                  <div key={r.title} className="post-rating-row">
                    <span className="post-rating-title">{r.title}</span>
                    <span className="post-rating-scores">
                      {r.tmdb && <span className="score-badge tmdb">TMDB {r.tmdb}</span>}
                      {r.imdb && <span className="score-badge imdb">IMDb {r.imdb}</span>}
                      {r.rotten_tomatoes && <span className="score-badge rt">RT {r.rotten_tomatoes}</span>}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="post-card-footer">
            <span className="post-card-source">Powered by Gemini AI</span>
            <span className="post-card-listen">cinevox.ai</span>
          </div>
        </div>
      )}
    </div>
  );
}
