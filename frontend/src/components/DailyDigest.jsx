import React, { useState, useEffect, useRef, useCallback } from 'react';
import { getDigest } from '../api';
import './DailyDigest.css';

/**
 * Convert base64 WAV to a playable blob URL.
 */
function wavToUrl(base64Wav) {
  const binary = atob(base64Wav);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i);
  }
  const blob = new Blob([bytes.buffer], { type: 'audio/wav' });
  return URL.createObjectURL(blob);
}

export default function DailyDigest() {
  const [digest, setDigest] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [audioUrl, setAudioUrl] = useState(null);
  const audioRef = useRef(null);

  const fetchDigest = useCallback(async () => {
    setLoading(true);
    setError(null);
    setIsPlaying(false);
    setCurrentTime(0);
    if (audioUrl) URL.revokeObjectURL(audioUrl);
    setAudioUrl(null);
    try {
      const data = await getDigest();
      setDigest(data);
      if (data.audio_base64) {
        setAudioUrl(wavToUrl(data.audio_base64));
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchDigest(); }, [fetchDigest]);

  function togglePlay() {
    if (!audioRef.current || !audioUrl) return;
    if (isPlaying) {
      audioRef.current.pause();
    } else {
      audioRef.current.play().catch(() => setIsPlaying(false));
    }
  }

  function handleScrub(e) {
    const time = parseFloat(e.target.value);
    if (audioRef.current) {
      audioRef.current.currentTime = time;
      setCurrentTime(time);
    }
  }

  function formatTime(t) {
    const m = Math.floor(t / 60);
    const s = Math.floor(t % 60);
    return `${m}:${s.toString().padStart(2, '0')}`;
  }

  // Split script into sentences for live transcript
  const sentences = digest?.script?.split(/(?<=[.!?])\s+/) || [];
  const activeSentenceIndex = duration > 0
    ? Math.min(Math.floor((currentTime / duration) * sentences.length), sentences.length - 1)
    : -1;

  if (loading) {
    return (
      <div className="digest-section">
        <div className="digest-header">
          <span className="digest-badge">Live</span>
          <h2 className="digest-title">CineVox Daily</h2>
        </div>
        <div className="digest-loading">
          <span className="digest-spinner" />
          <span>Generating today's film digest with Google Search...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="digest-section">
        <div className="digest-header">
          <span className="digest-badge">Live</span>
          <h2 className="digest-title">CineVox Daily</h2>
        </div>
        <div className="digest-error">
          <p>{error}</p>
          <button className="digest-retry-btn" onClick={fetchDigest}>Retry</button>
        </div>
      </div>
    );
  }

  if (!digest) return null;

  const progress = duration > 0 ? (currentTime / duration) * 100 : 0;

  return (
    <div className="digest-section">
      <div className="digest-header">
        <span className="digest-badge">Live</span>
        <h2 className="digest-title">CineVox Daily</h2>
        <span className="digest-date">{digest.date}</span>
      </div>

      {/* Video Teaser */}
      {digest.video_url && (
        <div className="digest-video">
          <video
            className="digest-video-player"
            src={digest.video_url}
            controls
            muted
            autoPlay
            loop
            playsInline
          />
        </div>
      )}

      {/* Player */}
      <div className="digest-player">
        <div className="digest-player-top">
          <button
            className={`digest-play-btn ${isPlaying ? 'playing' : ''}`}
            onClick={togglePlay}
            disabled={!audioUrl}
            aria-label={isPlaying ? 'Pause' : 'Play'}
          >
            {isPlaying ? (
              <svg viewBox="0 0 24 24" width="24" height="24">
                <rect x="6" y="4" width="4" height="16" fill="currentColor" />
                <rect x="14" y="4" width="4" height="16" fill="currentColor" />
              </svg>
            ) : (
              <svg viewBox="0 0 24 24" width="24" height="24">
                <polygon points="6,3 20,12 6,21" fill="currentColor" />
              </svg>
            )}
          </button>
          <div className="digest-player-info">
            <p className="digest-player-label">CineVox Daily</p>
          </div>
          <button className="digest-refresh-btn" onClick={fetchDigest} title="Refresh">
            <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M1 4v6h6M23 20v-6h-6" />
              <path d="M20.49 9A9 9 0 0 0 5.64 5.64L1 10m22 4l-4.64 4.36A9 9 0 0 1 3.51 15" />
            </svg>
          </button>
        </div>

        <div className="digest-progress-wrap">
          <input
            type="range"
            className="digest-scrubber"
            min="0"
            max={duration || 0}
            step="0.1"
            value={currentTime}
            onChange={handleScrub}
          />
          <div className="digest-progress-bar">
            <div className="digest-progress-fill" style={{ width: `${progress}%` }} />
          </div>
        </div>
        <div className="digest-time-row">
          <span>{formatTime(currentTime)}</span>
          <span>{formatTime(duration)}</span>
        </div>

        {audioUrl && (
          <audio
            ref={audioRef}
            src={audioUrl}
            onTimeUpdate={() => audioRef.current && setCurrentTime(audioRef.current.currentTime)}
            onLoadedMetadata={() => audioRef.current && setDuration(audioRef.current.duration)}
            onEnded={() => setIsPlaying(false)}
            onPause={() => setIsPlaying(false)}
            onPlay={() => setIsPlaying(true)}
            style={{ display: 'none' }}
          />
        )}
      </div>

      {/* Live Transcript */}
      <div className="digest-transcript">
        <p className="digest-transcript-label">Live Transcript</p>
        <div className="digest-transcript-body">
          {sentences.map((sentence, i) => (
            <span
              key={i}
              className={`digest-sentence ${i === activeSentenceIndex ? 'active' : ''}`}
            >
              {sentence}{' '}
            </span>
          ))}
        </div>
      </div>

      {/* Sources */}
      {digest.sources && digest.sources.length > 0 && (
        <div className="digest-sources">
          <p className="digest-sources-label">Sources</p>
          <div className="digest-sources-list">
            {digest.sources.map((src, i) => (
              <a
                key={i}
                href={src.uri}
                target="_blank"
                rel="noopener noreferrer"
                className="digest-source-link"
              >
                {src.title || 'Source'}
                <svg viewBox="0 0 24 24" width="10" height="10" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6M15 3h6v6M10 14L21 3" />
                </svg>
              </a>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
