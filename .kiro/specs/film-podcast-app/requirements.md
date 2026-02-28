# Requirements Document

## Introduction

The Film Review & News Podcast App aggregates written movie reviews from TMDB, Reddit, and OMDb, along with the latest movie news, and automatically converts them into a 1-3 minute AI-narrated podcast. The app targets aspiring film enthusiasts who want a quick, curated audio summary without reading multiple sources. It leverages the Gemini API (via Google GenAI SDK) for text summarization, sentiment analysis, narration script generation, and long-context memory across episodes. A web-based frontend allows users to select genres, directors, or trending films, and the backend orchestrates content aggregation, AI processing, and audio generation.

## Glossary

- **App**: The Film Review & News Podcast application, encompassing the React frontend and FastAPI Python backend.
- **Review_Aggregator**: The backend module responsible for fetching and combining movie reviews from TMDB, Reddit (via PRAW), and OMDb.
- **Summarizer**: The Gemini API-powered module that condenses multiple reviews and news articles into concise summaries.
- **Sentiment_Analyzer**: The Gemini API-powered module that classifies review sentiment as positive, negative, or mixed and extracts trending opinions.
- **Script_Generator**: The Gemini API-powered module that converts summaries and sentiment data into a natural, engaging narration script suitable for podcast audio.
- **Audio_Generator**: The module that converts narration scripts into spoken audio using an AI TTS model (Lyria or equivalent).
- **Podcast**: The final audio output file (MP3) containing the AI-narrated summary of reviews and news, targeting 10–20 minutes in length.
- **User_Preferences**: The set of user-selected genres, directors, or trending film topics that personalize podcast content.
- **Episode_Memory**: The Gemini long-context memory module that maintains awareness of trending topics and recurring franchises across podcast episodes.
- **TMDB_Client**: The client module that interfaces with The Movie Database API for movie metadata, ratings, and news.
- **Reddit_Client**: The client module that interfaces with the Reddit API via PRAW to fetch movie discussion threads and reviews.
- **OMDb_Client**: The client module that interfaces with the OMDb API for movie ratings and quick metadata lookups.
- **Frontend**: The React-based user interface for selecting genres, news topics, and triggering podcast generation.

## Requirements

### Requirement 1: Movie Metadata Retrieval

**User Story:** As a film enthusiast, I want the app to retrieve movie metadata from multiple sources, so that I have comprehensive and accurate information about the movies being reviewed.

#### Acceptance Criteria

1. WHEN a user selects a movie title, THE TMDB_Client SHALL retrieve the movie metadata including title, release date, genre, director, cast, and average rating from the TMDB API.
2. WHEN a user selects a movie title, THE OMDb_Client SHALL retrieve the movie ratings and plot summary from the OMDb API.
3. IF the TMDB API returns an error or is unavailable, THEN THE Review_Aggregator SHALL log the error and continue processing with data from the remaining available sources.
4. IF the OMDb API returns an error or is unavailable, THEN THE Review_Aggregator SHALL log the error and continue processing with data from the remaining available sources.
5. WHEN metadata is retrieved from multiple sources, THE Review_Aggregator SHALL merge the metadata into a single unified movie record, preferring TMDB data for conflicts.

### Requirement 2: Review Aggregation from Reddit

**User Story:** As a film enthusiast, I want the app to collect real user reviews and discussions from Reddit, so that I get authentic community opinions about movies.

#### Acceptance Criteria

1. WHEN a movie title is provided, THE Reddit_Client SHALL search relevant subreddits (r/movies, r/MovieReviews, r/flicks) for discussion threads and reviews using the PRAW library.
2. THE Reddit_Client SHALL retrieve a minimum of 3 and a maximum of 10 top-level comments or posts per movie from Reddit.
3. IF the Reddit API returns an error or rate-limits the request, THEN THE Reddit_Client SHALL retry the request up to 3 times with exponential backoff.
4. IF the Reddit API remains unavailable after retries, THEN THE Review_Aggregator SHALL log the failure and proceed with reviews from other sources.
5. WHEN reviews are retrieved, THE Reddit_Client SHALL include the comment score, author, and subreddit source for each review.

### Requirement 3: Text Summarization via Gemini API

**User Story:** As a film enthusiast, I want aggregated reviews and news to be summarized into concise highlights, so that I get the key opinions without redundancy.

#### Acceptance Criteria

1. WHEN aggregated reviews and news articles are provided, THE Summarizer SHALL use the Gemini API (via google-genai SDK) to generate a concise summary extracting key opinions, highlights, and consensus points.
2. THE Summarizer SHALL produce a summary of 200–500 words per movie from the aggregated source material.
3. WHEN fewer than 3 reviews are available for a movie, THE Summarizer SHALL indicate limited source coverage in the summary output.
4. IF the Gemini API returns an error, THEN THE Summarizer SHALL retry the request up to 2 times before returning an error status to the caller.
5. THE Summarizer SHALL preserve attribution by tagging summary points with the originating source (TMDB, Reddit, or OMDb).

### Requirement 4: Sentiment Analysis via Gemini API

**User Story:** As a film enthusiast, I want to know the overall sentiment and trending opinions about a movie, so that I can quickly gauge critical and audience reception.

#### Acceptance Criteria

1. WHEN aggregated reviews are provided, THE Sentiment_Analyzer SHALL use the Gemini API to classify the overall sentiment for each movie as positive, negative, or mixed.
2. THE Sentiment_Analyzer SHALL extract up to 5 key sentiment highlights per movie, each labeled with the sentiment polarity (positive or negative) and a brief supporting quote or paraphrase.
3. WHEN reviews contain conflicting opinions, THE Sentiment_Analyzer SHALL identify and report the primary points of disagreement.
4. THE Sentiment_Analyzer SHALL assign a confidence score between 0.0 and 1.0 to the overall sentiment classification.
5. IF the Gemini API returns an error during sentiment analysis, THEN THE Sentiment_Analyzer SHALL retry the request up to 2 times before returning an error status.

### Requirement 5: Podcast Narration Script Generation

**User Story:** As a film enthusiast, I want the summarized content to be converted into an engaging narration script, so that the podcast sounds natural and entertaining.

#### Acceptance Criteria

1. WHEN summaries and sentiment data are provided, THE Script_Generator SHALL use the Gemini API to produce a narration script structured with an introduction, per-movie segments, and a closing summary.
2. THE Script_Generator SHALL generate a script targeting 1,500–3,000 words to produce a podcast between 10 and 20 minutes in length.
3. THE Script_Generator SHALL incorporate sentiment highlights into the narration, using conversational transitions between positive and negative points.
4. WHEN multiple movies are included, THE Script_Generator SHALL generate smooth transitions between movie segments.
5. THE Script_Generator SHALL format the script with speaker cues and paragraph breaks suitable for TTS processing.

### Requirement 6: Audio Generation (Text-to-Speech)

**User Story:** As a film enthusiast, I want the narration script to be converted into high-quality spoken audio, so that I can listen to the podcast on the go.

#### Acceptance Criteria

1. WHEN a narration script is provided, THE Audio_Generator SHALL convert the script into spoken audio and output an MP3 file.
2. THE Audio_Generator SHALL produce audio with a consistent speaking pace between 130 and 160 words per minute.
3. THE Audio_Generator SHALL produce a final podcast audio file between 10 and 20 minutes in duration.
4. IF the TTS service returns an error, THEN THE Audio_Generator SHALL retry the request up to 2 times before returning an error status.
5. WHEN the script contains speaker cues or paragraph breaks, THE Audio_Generator SHALL insert natural pauses of 0.5–1.5 seconds at those points.

### Requirement 7: User Preference Selection via Frontend

**User Story:** As a film enthusiast, I want to select my preferred genres, directors, or trending films, so that the podcast content is personalized to my interests.

#### Acceptance Criteria

1. THE Frontend SHALL display a React-based interface allowing the user to select one or more genres from a predefined list.
2. THE Frontend SHALL allow the user to search for and select specific movie titles for inclusion in the podcast.
3. THE Frontend SHALL allow the user to select a "trending films" option that automatically includes currently popular movies.
4. WHEN the user submits preferences, THE Frontend SHALL pass the selected genres, movie titles, and options to the backend for processing.
5. THE Frontend SHALL display a progress indicator while the podcast is being generated.
6. WHEN podcast generation is complete, THE Frontend SHALL provide an audio player and a download link for the generated MP3 file.

### Requirement 8: Episode Continuity via Long-Context Memory

**User Story:** As a film enthusiast, I want the podcast to reference previous episodes and maintain awareness of trending topics, so that the listening experience feels continuous and informed.

#### Acceptance Criteria

1. WHEN generating a new podcast episode, THE Episode_Memory SHALL provide the Script_Generator with a context summary of topics, movies, and opinions covered in the previous 5 episodes.
2. THE Episode_Memory SHALL track recurring movie franchises and directors mentioned across episodes.
3. WHEN a movie franchise or director appears in a new episode that was covered previously, THE Script_Generator SHALL reference the prior coverage in the narration.
4. THE Episode_Memory SHALL store episode context summaries persistently so that context is retained across application restarts.
5. IF no previous episode data exists, THEN THE Episode_Memory SHALL indicate to the Script_Generator that the current episode is the first in the series.

### Requirement 9: End-to-End Podcast Generation Pipeline

**User Story:** As a film enthusiast, I want to trigger a single action that produces a complete podcast from my preferences, so that the experience is seamless and automated.

#### Acceptance Criteria

1. WHEN the user submits preferences via the Frontend, THE App SHALL orchestrate the full pipeline: metadata retrieval, review aggregation, summarization, sentiment analysis, script generation, and audio generation in sequence.
2. THE App SHALL complete the full pipeline and deliver a podcast audio file within 5 minutes for a selection of up to 3 movies.
3. IF any pipeline stage fails after retries, THEN THE App SHALL report the specific failure stage and reason to the user via the Frontend.
4. WHEN the pipeline completes successfully, THE App SHALL store the generated podcast metadata (title, date, movies covered, duration) for episode history.
5. THE App SHALL log the processing time for each pipeline stage for monitoring and debugging purposes.

### Requirement 10: Gemini API Integration via Google GenAI SDK

**User Story:** As a developer, I want all Gemini API interactions to use the official Google GenAI SDK, so that the integration is maintainable and leverages the latest Gemini capabilities.

#### Acceptance Criteria

1. THE App SHALL use the google-genai Python SDK for all interactions with the Gemini API, including summarization, sentiment analysis, and script generation.
2. THE App SHALL load the Gemini API key from the .env file using environment variable configuration.
3. THE App SHALL configure the Gemini model with appropriate parameters (temperature, max tokens) for each task: summarization, sentiment analysis, and script generation.
4. IF the Gemini API key is missing or invalid, THEN THE App SHALL display a clear error message to the user and halt processing.
5. WHEN making Gemini API calls, THE App SHALL implement request rate limiting to stay within API quota limits.
