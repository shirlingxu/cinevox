import React, { useState, useEffect, useRef } from 'react';
import { getStatus } from '../api';
import './ProgressIndicator.css';

const STAGES = ['metadata', 'reviews', 'summarization', 'sentiment', 'script', 'audio', 'mixing', 'post', 'complete'];

const STAGE_LABELS = {
  metadata: 'Fetching movie data',
  reviews: 'Collecting reviews',
  summarization: 'Summarizing reviews',
  sentiment: 'Analyzing sentiment',
  script: 'Writing narration',
  audio: 'Generating audio',
  mixing: 'Mixing background music',
  post: 'Creating cover art',
  complete: 'Broadcast ready',
};

function stageProgress(stage) {
  const idx = STAGES.indexOf(stage);
  if (idx === -1) return 0;
  return Math.round(((idx + 1) / STAGES.length) * 100);
}

function formatElapsed(seconds) {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

export default function ProgressIndicator({ podcastId, onComplete, onRetry }) {
  const [stage, setStage] = useState('metadata');
  const [error, setError] = useState(null);
  const [elapsed, setElapsed] = useState(0);
  const startRef = useRef(Date.now());
  const timerRef = useRef(null);
  const pollRef = useRef(null);

  useEffect(() => {
    startRef.current = Date.now();
    timerRef.current = setInterval(() => {
      setElapsed(Math.floor((Date.now() - startRef.current) / 1000));
    }, 1000);
    return () => clearInterval(timerRef.current);
  }, [podcastId]);

  useEffect(() => {
    let cancelled = false;
    async function poll() {
      try {
        const data = await getStatus(podcastId);
        if (cancelled) return;
        setStage(data.stage);
        if (data.stage === 'failed') {
          setError(data.error || 'An unexpected error occurred.');
          clearInterval(timerRef.current);
          return;
        }
        if (data.stage === 'complete') {
          clearInterval(timerRef.current);
          onComplete(data);
          return;
        }
      } catch (err) {
        if (cancelled) return;
      }
      pollRef.current = setTimeout(poll, 2000);
    }
    poll();
    return () => { cancelled = true; clearTimeout(pollRef.current); };
  }, [podcastId, onComplete]);

  const progress = stageProgress(stage);
  const currentIdx = STAGES.indexOf(stage);

  return (
    <div className="progress-indicator" role="status" aria-live="polite">
      <div className="progress-banner">
        <span className="live-dot" />
        <span className="progress-banner-text">Processing</span>
      </div>

      <div className="progress-body">
        <h2 className="progress-heading">Building Your Broadcast</h2>

        <div className="ticker" aria-hidden="true">
          {[...Array(9)].map((_, i) => <div key={i} className="ticker-bar" />)}
        </div>

        <div className="progress-track" role="progressbar" aria-valuenow={progress} aria-valuemin={0} aria-valuemax={100}>
          <div className="progress-fill" style={{ width: `${progress}%` }} />
        </div>

        {!error && (
          <>
            <p className="stage-label">{STAGE_LABELS[stage] || stage}</p>
            <p className="elapsed-time">Elapsed {formatElapsed(elapsed)}</p>
          </>
        )}

        {error && (
          <div className="error-block" role="alert">
            <p className="error-text">{error}</p>
            <button className="retry-btn" onClick={onRetry}>Retry</button>
          </div>
        )}

        <div className="stage-steps" aria-label="Pipeline stages">
          {STAGES.filter((s) => s !== 'complete').map((s, i) => {
            let cls = 'stage-step';
            if (i < currentIdx) cls += ' done';
            else if (i === currentIdx && !error) cls += ' current';
            return (
              <span key={s} className={cls}>
                <span className="step-dot" />
                {s}
              </span>
            );
          })}
        </div>
      </div>
    </div>
  );
}
