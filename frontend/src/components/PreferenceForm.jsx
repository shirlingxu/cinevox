import React, { useState, useEffect, useRef } from 'react';
import { getGenres, generatePodcast, searchMovies } from '../api';
import './PreferenceForm.css';

export default function PreferenceForm({ onGenerate }) {
  const [genres, setGenres] = useState([]);
  const [genresLoading, setGenresLoading] = useState(true);
  const [selectedGenres, setSelectedGenres] = useState([]);
  const [selectedMovies, setSelectedMovies] = useState([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [suggestions, setSuggestions] = useState([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [includeTrending, setIncludeTrending] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const searchRef = useRef(null);
  const debounceRef = useRef(null);

  useEffect(() => {
    let cancelled = false;
    getGenres()
      .then((data) => { if (!cancelled) setGenres(data); })
      .catch(() => {})
      .finally(() => { if (!cancelled) setGenresLoading(false); });
    return () => { cancelled = true; };
  }, []);

  // Close suggestions on outside click
  useEffect(() => {
    function handleClick(e) {
      if (searchRef.current && !searchRef.current.contains(e.target)) {
        setShowSuggestions(false);
      }
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  function handleSearchChange(e) {
    const val = e.target.value;
    setSearchQuery(val);

    clearTimeout(debounceRef.current);
    if (val.trim().length < 2) {
      setSuggestions([]);
      setShowSuggestions(false);
      return;
    }

    debounceRef.current = setTimeout(async () => {
      const results = await searchMovies(val.trim());
      // Filter out already-selected movies
      const filtered = results.filter(
        (r) => !selectedMovies.some((m) => m.id === r.id)
      );
      setSuggestions(filtered);
      setShowSuggestions(filtered.length > 0);
    }, 300);
  }

  function selectMovie(movie) {
    setSelectedMovies((prev) => [...prev, movie]);
    setSearchQuery('');
    setSuggestions([]);
    setShowSuggestions(false);
  }

  function removeMovie(id) {
    setSelectedMovies((prev) => prev.filter((m) => m.id !== id));
  }

  function toggleGenre(name) {
    setSelectedGenres((prev) =>
      prev.includes(name) ? prev.filter((g) => g !== name) : [...prev, name]
    );
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    const titles = selectedMovies.map((m) => m.title);
    try {
      const result = await generatePodcast({
        genres: selectedGenres,
        movie_titles: titles,
        include_trending: includeTrending,
      });
      onGenerate(result.podcast_id);
    } catch (err) {
      setError(err.message || 'Something went wrong.');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form className="preference-form" onSubmit={handleSubmit}>
      <p className="form-section-label">New Podcast</p>
      <h2 className="form-heading">Generate Episode</h2>

      <div className="form-group">
        <label className="form-label">Select Genres</label>
        {genresLoading ? (
          <p className="genres-loading">Loading...</p>
        ) : (
          <div className="genre-grid" role="group" aria-label="Genre selection">
            {genres.map((genre) => {
              const sel = selectedGenres.includes(genre.name);
              return (
                <label key={genre.id} className={`genre-chip${sel ? ' selected' : ''}`}>
                  <input type="checkbox" checked={sel} onChange={() => toggleGenre(genre.name)} aria-label={genre.name} />
                  {genre.name}
                </label>
              );
            })}
          </div>
        )}
      </div>

      <div className="form-group" ref={searchRef}>
        <label className="form-label" htmlFor="movie-search">Search Movies</label>
        <div className="search-wrapper">
          <input
            id="movie-search"
            className="text-input"
            type="text"
            placeholder="Type to search..."
            value={searchQuery}
            onChange={handleSearchChange}
            onFocus={() => { if (suggestions.length > 0) setShowSuggestions(true); }}
            autoComplete="off"
          />
          {showSuggestions && (
            <ul className="suggestions-list" role="listbox">
              {suggestions.map((movie) => (
                <li key={movie.id} className="suggestion-item" role="option" onClick={() => selectMovie(movie)}>
                  {movie.poster ? (
                    <img className="suggestion-poster" src={movie.poster} alt="" />
                  ) : (
                    <div className="suggestion-poster suggestion-poster-empty" />
                  )}
                  <div className="suggestion-info">
                    <span className="suggestion-title">{movie.title}</span>
                    <span className="suggestion-meta">
                      {movie.year}{movie.rating ? ` / ${movie.rating.toFixed(1)}` : ''}
                    </span>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>

        {selectedMovies.length > 0 && (
          <div className="selected-movies">
            {selectedMovies.map((movie) => (
              <span key={movie.id} className="selected-movie-chip">
                {movie.title}
                {movie.year ? ` (${movie.year})` : ''}
                <button type="button" className="remove-movie" onClick={() => removeMovie(movie.id)} aria-label={`Remove ${movie.title}`}>
                  x
                </button>
              </span>
            ))}
          </div>
        )}
      </div>

      <div className="form-group">
        <label className={`trending-toggle${includeTrending ? ' active' : ''}`}>
          <input type="checkbox" checked={includeTrending} onChange={(e) => setIncludeTrending(e.target.checked)} />
          Include trending films
        </label>
      </div>

      <button type="submit" className="submit-btn" disabled={submitting}>
        {submitting ? (<><span className="spinner" aria-hidden="true" />Generating...</>) : 'Go Live'}
      </button>

      {error && <p className="error-msg" role="alert">{error}</p>}
    </form>
  );
}
