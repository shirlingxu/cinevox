# CineVox

AI-powered film review podcast platform. Aggregates movie reviews from TMDB, OMDb, and Reddit, processes them through Gemini for summarization and sentiment analysis, generates a two-host conversational podcast script, and produces narrated audio via Gemini TTS. Includes a daily film digest powered by Google Search grounding.

Built for the Gemini 3 NYC Hackathon (Entertainment and Gaming theme).

---

## Table of Contents

- [Features](#features)
- [System Design](#system-design)
- [High-Level Architecture](#high-level-architecture)
- [Pipeline Flow](#pipeline-flow)
- [Project Structure](#project-structure)
- [Tech Stack](#tech-stack)
- [Setup](#setup)
- [Running](#running)
- [API Endpoints](#api-endpoints)
- [Environment Variables](#environment-variables)

---

## Features

- Multi-source movie data aggregation (TMDB, OMDb, Reddit public JSON)
- AI summarization and sentiment analysis via Gemini 2.5 Flash
- Two-host conversational podcast script generation (Alex and Maya)
- Multi-speaker TTS audio generation via Gemini TTS
- AI-generated background music via Lyria RealTime, mixed under speech with ducking and crossfades
- AI-generated cover images via Nano Banana Pro
- Daily Film Digest with Google Search grounding and live transcript
- Episode memory with cross-episode continuity
- Platform feed with episode cards, ratings, and inline audio playback
- Studio for creating new podcast episodes

---

## System Design

### High-Level Architecture

```
+--------------------------------------------------+
|                  React Frontend                   |
|                                                   |
|  +-------------+  +----------+  +--------------+  |
|  | Platform    |  | Studio   |  | Daily Digest |  |
|  | Feed        |  | (Create) |  | (Grounded)   |  |
|  +------+------+  +----+-----+  +------+-------+  |
|         |              |               |           |
+---------+--------------+---------------+-----------+
          |              |               |
          v              v               v
+--------------------------------------------------+
|               FastAPI Backend                     |
|                                                   |
|  +--------------------------------------------+  |
|  |          Pipeline Orchestrator              |  |
|  |                                            |  |
|  |  Metadata -> Reviews -> Summarize ->       |  |
|  |  Sentiment -> Script -> Audio -> Mix -> Post|  |
|  +--------------------------------------------+  |
|                                                   |
|  +------------+  +----------+  +--------------+  |
|  | Data       |  | Gemini   |  | Audio / Post |  |
|  | Clients    |  | AI       |  | Generation   |  |
|  | (TMDB,     |  | (Summary,|  | (TTS, Lyria  |  |
|  |  OMDb,     |  |  Sent.,  |  |  RealTime,   |  |
|  |  Reddit)   |  |  Script) |  |  Nano Banana)|  |
|  +------------+  +----------+  +--------------+  |
|                                                   |
|  +------------+  +-----------------------------+  |
|  | Episode    |  | Daily Digest               |  |
|  | Memory     |  | (Google Search Grounding + |  |
|  | (JSON)     |  |  TTS, cached per day)      |  |
|  +------------+  +-----------------------------+  |
+--------------------------------------------------+
          |
          v
+--------------------------------------------------+
|              File System (data/)                  |
|  episodes/*.mp3  |  memory.json  |  audio_assets/ |
|  digest/                                          |
+--------------------------------------------------+
```

### Pipeline Flow

This is the sequence of operations when a user creates a new podcast episode:

```
User submits preferences (movie titles, genres, trending toggle)
  |
  v
1. METADATA RETRIEVAL
   +-- TMDB: movie details, credits, keywords, reviews
   +-- OMDb: IMDb rating, Rotten Tomatoes score
   |   (merged into unified MovieRecord, TMDB preferred on conflict)
   v
2. REVIEW AGGREGATION
   +-- Reddit: public JSON from r/movies, r/MovieReviews, r/flicks
   |   (3-10 top comments per movie, no credentials required)
   v
3. SUMMARIZATION (Gemini 2.5 Flash, temp 0.3)
   +-- Generates 200-500 word review summary per movie
   +-- Includes source attribution
   v
4. SENTIMENT ANALYSIS (Gemini 2.5 Flash, temp 0.2)
   +-- Classifies overall sentiment (positive/negative/mixed)
   +-- Extracts highlights, assigns confidence score
   v
5. SCRIPT GENERATION (Gemini 2.5 Flash, temp 0.7)
   +-- Two-host format: Alex and Maya
   +-- 400-600 words targeting 2-3 minute podcast
   +-- Reads episode memory for cross-episode references
   v
6. AUDIO GENERATION (Gemini TTS)
   +-- Multi-speaker: Orus (Alex) and Aoede (Maya)
   +-- Script chunking for long content
   +-- Output: speech AudioSegment
   v
7. BACKGROUND AUDIO MIXING
   +-- Lyria RealTime generates genre/sentiment-aware background music
   +-- Genre-to-prompt mapping (horror -> dark orchestral, comedy -> upbeat indie, etc.)
   +-- Sentiment modifiers (positive -> bright major key, negative -> somber minor key)
   +-- Speech ducking: background reduced during narration, restored during pauses
   +-- Crossfades between movie segments, transition SFX
   +-- Falls back to static asset library if Lyria unavailable
   +-- Output: final mixed MP3
   v
8. POST GENERATION
   +-- Cover image via Nano Banana Pro (async)
   +-- Summary, keywords, tagline via Gemini 2.5 Flash
   +-- Rating badges (TMDB, IMDb, Rotten Tomatoes)
   v
9. SAVE TO MEMORY
   +-- Episode persisted to data/memory.json
   +-- Available in Platform feed and Episode Library
```

### Daily Digest Flow

The Daily Film Digest runs separately from the podcast pipeline:

```
GET /api/digest
  |
  v
Check cache (data/digest/daily_digest.json)
  |
  +-- Cache exists for today? --> Return cached response
  |
  +-- No cache / stale -->
        |
        v
      Google Search Grounding (Gemini 2.5 Flash)
        +-- Searches for top 3 film reviews from major publications
        +-- Searches for top 3 breaking film industry news
        +-- Generates 2-minute podcast script
        +-- Extracts grounding sources (URLs, titles)
        |
        v
      TTS Generation (Gemini TTS, voice: Zephyr)
        +-- PCM to WAV conversion
        +-- Base64 encoded for frontend playback
        |
        v
      Cache to disk (date-keyed, regenerates next day)
        |
        v
      Return: { script, audio_base64, sources, date }
```

### Component Interaction

```
                    +------------------+
                    |   User Browser   |
                    +--------+---------+
                             |
                    HTTP (port 8000)
                             |
                    +--------v---------+
                    |  FastAPI Server   |
                    |                   |
                    |  Static Files     |--- serves React build (frontend/dist/)
                    |  API Routes       |--- /api/*
                    +--------+---------+
                             |
              +--------------+--------------+
              |              |              |
     +--------v---+  +------v------+  +----v--------+
     | TMDB API   |  | OMDb API    |  | Reddit JSON |
     | (external) |  | (external)  |  | (external)  |
     +------------+  +-------------+  +-------------+
              |              |              |
              +--------------+--------------+
                             |
                    +--------v---------+
                    |   Gemini API     |
                    |                  |
                    |  - 2.5 Flash     |--- text generation
                    |  - TTS Preview   |--- audio generation
                    |  - Lyria RT      |--- background music
                    |  - Nano Banana   |--- image generation
                    |  - Google Search |--- grounding (digest)
                    +--------+---------+
                             |
                    +--------v---------+
                    |   File System    |
                    |                  |
                    |  data/episodes/  |--- MP3 + cover images
                    |  data/memory.json|--- episode history
                    |  data/digest/    |--- cached daily digest
                    +------------------+
```

---

## Project Structure

```
cinevox/
  backend/
    main.py                    FastAPI app, static file serving, all API routes
    config.py                  Environment config, API key loading
    pipeline.py                Pipeline orchestrator (9-stage sequential flow)
    models.py                  Pydantic data models
    clients/
      tmdb_client.py           TMDB API client (search, details, trending, genres)
      omdb_client.py           OMDb API client (ratings lookup)
      reddit_client.py         Reddit public JSON client (no credentials)
    ai/
      gemini_client.py         Shared Gemini SDK setup
      summarizer.py            Review summarization (temp 0.3)
      sentiment.py             Sentiment analysis (temp 0.2)
      script_generator.py      Two-host script generation (temp 0.7)
      post_generator.py        Cover image + post text generation
      daily_digest.py          Google Search grounded digest with caching
    audio/
      tts.py                   Gemini multi-speaker TTS, MP3 output
      selector.py              Lyria RealTime music generation + static asset fallback
      mixer.py                 Speech ducking, crossfades, background mixing
    memory/
      episode_memory.py        JSON-based episode persistence
  frontend/
    index.html
    vite.config.js
    src/
      App.jsx                  Main app with Platform/Studio tabs
      App.css                  Global theme (cinevox warm dark)
      api.js                   Backend API client functions
      components/
        PlatformFeed.jsx/css   Public feed with episode cards
        DailyDigest.jsx/css    Daily digest player with live transcript
        PreferenceForm.jsx/css Movie selection and preferences
        ProgressIndicator.jsx  Pipeline progress with stage tracking
        PodcastPlayer.jsx/css  Audio player with post card display
        EpisodeLibrary.jsx/css Past episodes list
  data/
    episodes/                  Generated MP3 and cover image files
    audio_assets/              Static fallback music, SFX, jingles + manifest
    memory.json                Episode history (auto-created)
    digest/                    Cached daily digest (auto-created)
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 19, Vite |
| Backend | Python 3.14, FastAPI, Uvicorn |
| AI Models | Gemini 2.5 Flash (text), Gemini TTS (audio), Lyria RealTime (music), Nano Banana Pro (images) |
| Search | Google Search Grounding (daily digest) |
| Data Sources | TMDB API, OMDb API, Reddit public JSON |
| Persistence | JSON files on disk |
| Styling | Custom CSS, warm dark theme with atmospheric gradients |
| Fonts | Inter, Cormorant Garamond, JetBrains Mono |

---

## Setup

### Prerequisites

- Python 3.12+
- Node.js 18+
- API keys for TMDB, OMDb, and Gemini

### Installation

```bash
# Clone
git clone git@github.com:shirlingxu/cinevox.git
cd cinevox
git checkout cinevox-podcast-app

# Backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Frontend
cd frontend
npm install
npm run build
cd ..

# Environment
cp .env.example .env
# Edit .env with your API keys
```

### Environment Variables

Create a `.env` file in the project root:

```
TMDB_API_KEY=your_tmdb_api_key
OMDB_API_KEY=your_omdb_api_key
GEMINI_API_KEY=your_gemini_api_key
```

Reddit credentials are optional. The app uses public JSON endpoints.

---

## Running

```bash
# Activate virtual environment
source .venv/bin/activate

# Start the server (serves both API and frontend)
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

Open `http://localhost:8000` in your browser.

- Platform tab: browse the feed and daily digest
- Studio tab: create new podcast episodes

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | /api/generate | Start podcast generation with user preferences |
| GET | /api/status/{id} | Poll pipeline progress |
| GET | /api/audio/{id} | Serve generated MP3 |
| GET | /api/episodes | List past episodes |
| GET | /api/genres | TMDB genre list |
| GET | /api/search?q= | Movie title autocomplete |
| POST | /api/post/{id} | Generate post card (cover image + summary) |
| GET | /api/post-data/{id} | Get pre-generated post data |
| GET | /api/post-image/{id} | Serve cover image |
| GET | /api/feed | Platform feed (all posted episodes) |
| GET | /api/digest | Daily film digest (cached per day) |
