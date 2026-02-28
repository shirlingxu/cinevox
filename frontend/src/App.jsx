import React, { useState, useCallback } from 'react';
import PreferenceForm from './components/PreferenceForm';
import ProgressIndicator from './components/ProgressIndicator';
import PodcastPlayer from './components/PodcastPlayer';
import EpisodeLibrary from './components/EpisodeLibrary';
import PlatformFeed from './components/PlatformFeed';
import './App.css';

function App() {
  const [page, setPage] = useState('studio');
  const [appState, setAppState] = useState('idle');
  const [podcastId, setPodcastId] = useState(null);
  const [podcastData, setPodcastData] = useState(null);

  function handleGenerate(id) {
    setPodcastId(id);
    setPodcastData(null);
    setAppState('generating');
  }

  const handleComplete = useCallback((data) => {
    setPodcastData(data);
    setAppState('complete');
  }, []);

  function handleRetry() {
    setAppState('idle');
  }

  function handleNewPodcast() {
    setPodcastId(null);
    setPodcastData(null);
    setAppState('idle');
  }

  function handleSelectEpisode(episode) {
    setPodcastId(episode.episode_id);
    setPodcastData({
      title: episode.title,
      movies_covered: episode.movies_covered,
    });
    setAppState('complete');
  }

  return (
    <div className="app">
      <header className="app-header">
        <span className="app-logo">Live</span>
        <h1 className="app-title">CineVox</h1>
        <nav className="app-nav">
          <button
            className={`nav-tab ${page === 'platform' ? 'active' : ''}`}
            onClick={() => setPage('platform')}
          >
            Platform
          </button>
          <button
            className={`nav-tab ${page === 'studio' ? 'active' : ''}`}
            onClick={() => setPage('studio')}
          >
            Studio
          </button>
        </nav>
      </header>

      <main className="app-content">
        {page === 'platform' && <PlatformFeed />}

        {page === 'studio' && (
          <>
            {appState === 'idle' && (
              <>
                <PreferenceForm onGenerate={handleGenerate} />
                <EpisodeLibrary onSelectEpisode={handleSelectEpisode} />
              </>
            )}
            {appState === 'generating' && podcastId && (
              <ProgressIndicator
                podcastId={podcastId}
                onComplete={handleComplete}
                onRetry={handleRetry}
              />
            )}
            {appState === 'complete' && podcastId && (
              <PodcastPlayer
                podcastId={podcastId}
                metadata={podcastData || {}}
                onNewPodcast={handleNewPodcast}
              />
            )}
          </>
        )}
      </main>

      <footer className="app-footer">
        <p>Powered by Gemini AI / TMDB / Reddit / OMDb</p>
      </footer>
    </div>
  );
}

export default App;
