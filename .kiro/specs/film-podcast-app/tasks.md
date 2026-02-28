# Implementation Plan: Film Review & News Podcast App

## Overview

Build a full-stack podcast generation app with a FastAPI backend and React frontend. The backend aggregates movie data from TMDB, Reddit, and OMDb, processes it through Gemini API (summarization, sentiment, script generation), generates audio via gTTS, and maintains episode memory via JSON persistence. Implementation proceeds bottom-up: config → models → data clients → AI modules → audio → memory → pipeline → API → frontend.

## Tasks

- [x] 1. Set up project structure, configuration, and data models
  - [x] 1.1 Create backend project skeleton with `requirements.txt` and `backend/config.py`
    - Create `backend/` directory structure matching the design (clients/, ai/, audio/, memory/)
    - Create `requirements.txt` with: fastapi, uvicorn, httpx, praw, google-genai, gtts, pydantic, python-dotenv, hypothesis, pytest
    - Implement `backend/config.py` to load API keys (TMDB_API_KEY, OMDB_API_KEY, GEMINI_API_KEY, REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET) from `.env` using `python-dotenv`
    - Validate that required keys are present and raise clear errors if missing
    - _Requirements: 10.2, 10.4_

  - [x] 1.2 Create Pydantic data models in `backend/models.py`
    - Implement all data models from the design: enums (SentimentPolarity, PipelineStage), request/response models (UserPreferences, Genre), movie data models (TMDBMovie, OMDbMovie, MovieRecord), review models (RedditReview, AggregatedReviews), AI output models (MovieSummary, SentimentHighlight, SentimentResult, NarrationScript), audio models (PodcastResult), pipeline models (PipelineStatus), and episode memory models (EpisodeSummary, EpisodeContext)
    - Include all Field validators (e.g., confidence between 0.0 and 1.0)
    - _Requirements: 1.1, 1.2, 1.5, 2.5, 3.1, 4.1, 4.4, 5.1, 6.1, 8.1, 9.4_

- [x] 2. Implement data source clients
  - [x] 2.1 Implement TMDB client in `backend/clients/tmdb_client.py`
    - Implement `TMDBClient` class with async methods: `search_movie`, `get_movie_details`, `get_trending`, `get_genres`
    - Use `httpx.AsyncClient` for HTTP requests with TMDB_API_KEY from config
    - Parse API responses into `TMDBMovie` models, extracting title, release_date, genres, director, cast, rating
    - Handle HTTP errors gracefully: log and return `None` on failure
    - _Requirements: 1.1, 1.3, 7.3_

  - [ ]* 2.2 Write property test for TMDB metadata parsing (Property 1)
    - **Property 1: TMDB Client parses all required metadata fields**
    - **Validates: Requirements 1.1**

  - [x] 2.3 Implement OMDb client in `backend/clients/omdb_client.py`
    - Implement `OMDbClient` class with async `get_movie` method
    - Use `httpx.AsyncClient` with OMDB_API_KEY from config
    - Parse API responses into `OMDbMovie` models, extracting imdb_rating, rotten_tomatoes, plot
    - Handle HTTP errors gracefully: log and return `None` on failure
    - _Requirements: 1.2, 1.4_

  - [ ]* 2.4 Write property test for OMDb parsing (Property 2)
    - **Property 2: OMDb Client parses ratings and plot**
    - **Validates: Requirements 1.2**

  - [x] 2.5 Implement Reddit client in `backend/clients/reddit_client.py`
    - Implement `RedditClient` class with `search_reviews` method using PRAW
    - Search subreddits r/movies, r/MovieReviews, r/flicks for movie discussions
    - Return 3–10 `RedditReview` objects per movie with text, score, author, subreddit
    - Implement retry with exponential backoff (up to 3 retries, delays 1s/2s/4s)
    - Handle PRAW exceptions and rate limits; log failures
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

  - [ ]* 2.6 Write property tests for Reddit client (Properties 5, 6)
    - **Property 5: Reddit review count bounds**
    - **Property 6: Reddit review fields are populated**
    - **Validates: Requirements 2.2, 2.5**

  - [x] 2.7 Implement metadata merge logic in `backend/pipeline.py` (partial — `_fetch_metadata` method)
    - Merge `TMDBMovie` and `OMDbMovie` into a unified `MovieRecord`
    - Prefer TMDB data for any conflicting fields
    - Handle cases where one or both sources return `None`
    - _Requirements: 1.5, 1.3, 1.4_

  - [ ]* 2.8 Write property tests for metadata merge and graceful degradation (Properties 3, 4)
    - **Property 3: Graceful degradation on data source failure**
    - **Property 4: Metadata merge prefers TMDB on conflict**
    - **Validates: Requirements 1.3, 1.4, 1.5, 2.4**

- [ ] 3. Checkpoint
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 4. Implement Gemini AI modules
  - [x] 4.1 Create shared Gemini client in `backend/ai/gemini_client.py`
    - Implement `get_gemini_client()` function using `google.genai` SDK
    - Load API key from config, validate presence
    - Implement rate limiter to throttle Gemini API calls within quota limits
    - _Requirements: 10.1, 10.2, 10.4, 10.5_

  - [ ]* 4.2 Write property test for rate limiting (Property 24)
    - **Property 24: Gemini API rate limiting**
    - **Validates: Requirements 10.5**

  - [x] 4.3 Implement Summarizer in `backend/ai/summarizer.py`
    - Implement `Summarizer` class with async `summarize` method
    - Configure Gemini with temperature=0.3 for factual output
    - Prompt instructs: produce 200–500 word summary, preserve source attribution, flag limited coverage when fewer than 3 reviews
    - Parse Gemini response into `MovieSummary` model
    - Retry up to 2 times on API errors
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

  - [ ]* 4.4 Write property tests for Summarizer (Properties 8, 9, 10)
    - **Property 8: Summary word count within bounds**
    - **Property 9: Limited coverage flag for sparse reviews**
    - **Property 10: Summary preserves source attribution**
    - **Validates: Requirements 3.2, 3.3, 3.5**

  - [x] 4.5 Implement Sentiment Analyzer in `backend/ai/sentiment.py`
    - Implement `SentimentAnalyzer` class with async `analyze` method
    - Configure Gemini with temperature=0.2 for analytical output
    - Prompt instructs: classify sentiment (positive/negative/mixed), extract up to 5 highlights with polarity, identify disagreements, assign confidence score 0.0–1.0
    - Parse Gemini response into `SentimentResult` model
    - Retry up to 2 times on API errors
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

  - [ ]* 4.6 Write property test for Sentiment Analyzer (Property 11)
    - **Property 11: SentimentResult structural invariants**
    - **Validates: Requirements 4.1, 4.2, 4.4**

  - [x] 4.7 Implement Script Generator in `backend/ai/script_generator.py`
    - Implement `ScriptGenerator` class with async `generate` method
    - Configure Gemini with temperature=0.7 for creative output
    - Prompt instructs: produce 1,500–3,000 word narration script with intro, per-movie segments, closing; incorporate sentiment highlights; include speaker cues and paragraph breaks for TTS; reference episode memory context for continuity
    - Accept `EpisodeContext` parameter; when provided, include references to prior episodes in narration
    - When `is_first_episode` is True, introduce the podcast series
    - Retry up to 2 times on API errors
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 8.3_

  - [ ]* 4.8 Write property tests for Script Generator (Properties 12, 13, 14)
    - **Property 12: Script structure contains required segments**
    - **Property 13: Script word count within bounds**
    - **Property 14: Script contains TTS formatting markers**
    - **Validates: Requirements 5.1, 5.2, 5.5**

- [ ] 5. Checkpoint
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 6. Implement audio generation and episode memory
  - [x] 6.1 Implement Audio Generator in `backend/audio/tts.py`
    - Implement `AudioGenerator` class with `generate` method using gTTS
    - Split script at paragraph breaks and speaker cues to insert natural pauses (0.5–1.5s silence)
    - Output MP3 files to `data/episodes/` directory
    - Retry up to 2 times on gTTS errors
    - Return file path of generated MP3
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

  - [ ]* 6.2 Write property tests for Audio Generator (Properties 15, 16, 17)
    - **Property 15: Audio generator produces valid MP3**
    - **Property 16: Audio speaking pace within bounds**
    - **Property 17: Audio duration within bounds**
    - **Validates: Requirements 6.1, 6.2, 6.3**

  - [x] 6.3 Implement Episode Memory in `backend/memory/episode_memory.py`
    - Implement `EpisodeMemory` class with JSON file persistence at `data/memory.json`
    - Implement `get_context(last_n=5)` returning `EpisodeContext` with recent episodes ordered most-recent-first
    - Implement `save_episode(episode)` to append episode summary and persist to disk
    - Implement `get_recurring_topics()` to track directors/franchises appearing in 2+ episodes
    - Handle corrupted/missing JSON gracefully: initialize empty state, log warning
    - When no previous episodes exist, set `is_first_episode=True` in context
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

  - [ ]* 6.4 Write property tests for Episode Memory (Properties 19, 20, 21)
    - **Property 19: Episode memory returns at most N recent episodes**
    - **Property 20: Recurring topics tracking**
    - **Property 21: Episode memory persistence round-trip**
    - **Validates: Requirements 8.1, 8.2, 8.4**

- [ ] 7. Checkpoint
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. Implement pipeline orchestrator and FastAPI endpoints
  - [x] 8.1 Complete Pipeline Orchestrator in `backend/pipeline.py`
    - Implement `PipelineOrchestrator.run()` method orchestrating the full sequence: metadata retrieval → review aggregation → summarization → sentiment analysis → script generation (with episode memory context) → audio generation
    - Track `PipelineStatus` with current stage, progress percentage, and per-stage timing
    - Handle stage failures: if a critical stage fails after retries, halt and return `PipelineStatus` with `stage=FAILED` and error message
    - Handle non-critical source failures: continue pipeline with reduced data
    - After successful completion, save episode to `EpisodeMemory` and store podcast metadata
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 8.1_

  - [ ]* 8.2 Write property tests for pipeline (Properties 7, 22, 23)
    - **Property 7: Service retry behavior**
    - **Property 22: Pipeline failure reports stage and reason**
    - **Property 23: Successful pipeline output completeness**
    - **Validates: Requirements 2.3, 3.4, 4.5, 6.4, 9.3, 9.4, 9.5**

  - [x] 8.3 Implement FastAPI endpoints in `backend/main.py`
    - Create FastAPI app with CORS middleware for React frontend
    - Implement `POST /api/generate`: accept `UserPreferences`, start pipeline (background task), return podcast_id
    - Implement `GET /api/status/{podcast_id}`: return current `PipelineStatus`
    - Implement `GET /api/audio/{podcast_id}`: serve generated MP3 file via `FileResponse`
    - Implement `GET /api/episodes`: return list of past episode metadata from memory
    - Implement `GET /api/genres`: return genre list from TMDB client
    - Handle missing/invalid API key with clear error response
    - _Requirements: 7.4, 9.1, 9.3, 10.4_

  - [ ]* 8.4 Write property test for user preferences round-trip (Property 18)
    - **Property 18: User preferences round-trip to backend**
    - **Validates: Requirements 7.4**

- [ ] 9. Implement React frontend
  - [x] 9.1 Set up React project and API client
    - Initialize React project in `frontend/` with Vite or Create React App
    - Create `frontend/src/api.js` with functions: `generatePodcast(preferences)`, `getStatus(podcastId)`, `getAudio(podcastId)`, `getEpisodes()`, `getGenres()`
    - Configure API base URL pointing to FastAPI backend
    - _Requirements: 7.4_

  - [x] 9.2 Implement PreferenceForm component
    - Create `frontend/src/components/PreferenceForm.jsx`
    - Genre multi-select dropdown populated from `/api/genres`
    - Movie title search input
    - "Trending Films" toggle checkbox
    - Submit button that calls `generatePodcast` with collected preferences
    - _Requirements: 7.1, 7.2, 7.3, 7.4_

  - [x] 9.3 Implement ProgressIndicator component
    - Create `frontend/src/components/ProgressIndicator.jsx`
    - Poll `/api/status/{id}` every 2 seconds after generation starts
    - Display current pipeline stage name and elapsed time
    - Show error message with retry button on `FAILED` status
    - _Requirements: 7.5, 9.3_

  - [x] 9.4 Implement PodcastPlayer component
    - Create `frontend/src/components/PodcastPlayer.jsx`
    - HTML5 `<audio>` player pointing to `/api/audio/{id}`
    - Download link for the MP3 file
    - Display episode metadata: title, movies covered, duration
    - _Requirements: 7.6_

  - [x] 9.5 Wire up App.jsx with all components
    - Create `frontend/src/App.jsx` integrating PreferenceForm, ProgressIndicator, and PodcastPlayer
    - Manage app state: idle → generating → complete/error
    - Show PreferenceForm initially, ProgressIndicator during generation, PodcastPlayer on completion
    - _Requirements: 7.1, 7.5, 7.6, 9.1_

- [ ] 10. Final checkpoint
  - Ensure all tests pass, ask the user if questions arise.
  - Verify end-to-end flow: user selects preferences → pipeline runs → audio plays in browser

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Audio generation (task 6.1) and Episode Memory (task 6.3) are core differentiators — not optional
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation between major phases
- Property tests validate universal correctness properties from the design document
- All Gemini API calls use the google-genai SDK per Requirement 10.1
