const API_BASE = '/api';

/**
 * Start podcast generation with user preferences.
 * @param {{ genres: string[], movie_titles: string[], include_trending: boolean }} preferences
 * @returns {Promise<{ podcast_id: string }>}
 */
export async function generatePodcast(preferences) {
  const res = await fetch(`${API_BASE}/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(preferences),
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || 'Failed to start podcast generation');
  }
  return res.json();
}

/**
 * Poll the pipeline status for a given podcast.
 * @param {string} podcastId
 * @returns {Promise<{ podcast_id: string, stage: string, progress_pct: number, error: string|null, stage_timings: object }>}
 */
export async function getStatus(podcastId) {
  const res = await fetch(`${API_BASE}/status/${podcastId}`);
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || 'Failed to get status');
  }
  return res.json();
}

/**
 * Get the audio URL for a completed podcast.
 * @param {string} podcastId
 * @returns {string}
 */
export function getAudio(podcastId) {
  return `${API_BASE}/audio/${podcastId}`;
}

/**
 * Fetch the list of past episodes.
 * @returns {Promise<Array>}
 */
export async function getEpisodes() {
  const res = await fetch(`${API_BASE}/episodes`);
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || 'Failed to fetch episodes');
  }
  return res.json();
}

/**
 * Fetch available genres from TMDB.
 * @returns {Promise<Array<{ id: number, name: string }>>}
 */
export async function getGenres() {
  const res = await fetch(`${API_BASE}/genres`);
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || 'Failed to fetch genres');
  }
  return res.json();
}

/**
 * Search TMDB for movies matching a query (autocomplete).
 * @param {string} query
 * @returns {Promise<Array<{ id: number, title: string, year: string, rating: number|null, poster: string|null }>>}
 */
export async function searchMovies(query) {
  const res = await fetch(`${API_BASE}/search?q=${encodeURIComponent(query)}`);
  if (!res.ok) return [];
  return res.json();
}

/**
 * Create a social post card for a podcast episode.
 * @param {string} podcastId
 * @returns {Promise<{ podcast_id, title, movies_covered, summary, keywords, tagline, ratings, image_url, audio_url }>}
 */
export async function createPost(podcastId) {
  const res = await fetch(`${API_BASE}/post/${podcastId}`, { method: 'POST' });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || 'Failed to create post');
  }
  return res.json();
}

/**
 * Get pre-generated post data for a podcast episode.
 * @param {string} podcastId
 * @returns {Promise<{ podcast_id, title, movies_covered, summary, keywords, tagline, ratings, image_url, audio_url }>}
 */
export async function getPostData(podcastId) {
  const res = await fetch(`${API_BASE}/post-data/${podcastId}`);
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || 'Failed to get post data');
  }
  return res.json();
}

/**
 * Fetch the platform feed — all posted episodes with cover images, summaries, ratings.
 * @returns {Promise<Array<{ podcast_id, title, date, movies_covered, summary, keywords, tagline, ratings, image_url, audio_url }>>}
 */
export async function getFeed() {
  const res = await fetch(`${API_BASE}/feed`);
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || 'Failed to fetch feed');
  }
  return res.json();
}

/**
 * Fetch the daily film digest — grounded search, script, and TTS audio.
 * @returns {Promise<{ script: string, audio_base64: string|null, sources: Array<{title, uri}>, date: string }>}
 */
export async function getDigest() {
  const res = await fetch(`${API_BASE}/digest`);
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || 'Failed to fetch digest');
  }
  return res.json();
}
