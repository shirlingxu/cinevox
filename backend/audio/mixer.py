"""Audio Mixer — layers background music under speech with ducking, crossfades, and transitions.

Takes a speech AudioSegment from TTS and mixes it with Lyria-generated
(or fallback static) background music, transition SFX, and jingles.
"""

import logging
import math

from pydub import AudioSegment
from pydub.silence import detect_silence

from backend.audio.selector import AudioSelector

logger = logging.getLogger(__name__)

# Mixing constants
BACKGROUND_DB_BELOW_SPEECH = -21  # Target: -18 to -24 dB below speech
DUCK_DB = -9  # Reduce background by this during speech
PAUSE_THRESHOLD_MS = 1500  # Pauses longer than this restore background volume
SILENCE_THRESH_DBFS = -40  # dBFS threshold for silence detection
CROSSFADE_MS = 3000  # 2-4 seconds crossfade between segments
FADE_MS = 500  # Fade duration at loop points


class AudioMixer:
    """Mixes background music under podcast speech audio."""

    def __init__(self, selector: AudioSelector):
        self._selector = selector

    async def mix(
        self,
        speech: AudioSegment,
        movie_segments: list[str],
        genres_per_movie: dict[str, list[str]],
        sentiments_per_movie: dict[str, str],
    ) -> AudioSegment:
        """Produce the final mixed AudioSegment.

        1. Add intro jingle
        2. For each movie segment:
           a. Insert transition SFX
           b. Generate/select background track for genre + sentiment
           c. Loop/trim track to segment duration
           d. Apply speech ducking to background
           e. Overlay background under speech
           f. Crossfade at segment boundary
        3. Add outro jingle
        """
        if len(speech) == 0:
            logger.warning("Empty speech segment, skipping mixing")
            return speech

        # Normalize speech to consistent sample rate for mixing
        speech = speech.set_frame_rate(48000).set_channels(2).set_sample_width(2)

        # Estimate segment boundaries
        boundaries = self._estimate_segment_boundaries(speech, movie_segments)

        # Build mixed output
        mixed = AudioSegment.empty()

        # 1. Intro jingle
        intro = self._selector.get_intro_jingle()
        if intro:
            intro = intro.set_frame_rate(48000).set_channels(2).set_sample_width(2)
            intro = intro.fade_in(200).fade_out(300)
            mixed += intro
            logger.info("Added intro jingle: %.1fs", len(intro) / 1000.0)

        # 2. Process each movie segment
        for i, (start_ms, end_ms) in enumerate(boundaries):
            segment_name = (
                movie_segments[i] if i < len(movie_segments) else "unknown"
            )
            segment_speech = speech[start_ms:end_ms]
            segment_duration_s = len(segment_speech) / 1000.0

            # Get genres and sentiment for this segment
            genres = genres_per_movie.get(segment_name, [])
            sentiment = sentiments_per_movie.get(segment_name, "mixed")

            # a. Transition SFX
            if i > 0:
                dominant_genre = genres[0] if genres else "drama"
                sfx = self._selector.get_transition_sfx(dominant_genre)
                if sfx:
                    sfx = (
                        sfx.set_frame_rate(48000)
                        .set_channels(2)
                        .set_sample_width(2)
                    )
                    sfx = sfx[:3000]  # Cap at 3 seconds
                    mixed += sfx.fade_in(100).fade_out(200)
                    logger.info(
                        "Added transition SFX for %s: %.1fs",
                        segment_name,
                        len(sfx) / 1000.0,
                    )

            # b. Get background track (Lyria or fallback)
            bg_track = await self._selector.get_track(
                genres, sentiment, duration_seconds=min(segment_duration_s, 30.0)
            )

            if bg_track is not None:
                bg_track = (
                    bg_track.set_frame_rate(48000)
                    .set_channels(2)
                    .set_sample_width(2)
                )

                # c. Loop/trim to segment duration
                bg_track = self._loop_track(bg_track, len(segment_speech))

                # d. Set background level relative to speech
                bg_track = self._set_background_level(bg_track, segment_speech)

                # e. Apply ducking
                bg_track = self._apply_ducking(bg_track, segment_speech)

                # f. Overlay background under speech
                segment_mixed = bg_track.overlay(segment_speech)
            else:
                segment_mixed = segment_speech

            # g. Crossfade with previous segment
            if len(mixed) > 0 and i > 0 and len(mixed) >= CROSSFADE_MS:
                mixed = mixed.append(segment_mixed, crossfade=CROSSFADE_MS)
            else:
                mixed += segment_mixed

            logger.info(
                "Mixed segment %d/%d: %s (%.1fs)",
                i + 1,
                len(boundaries),
                segment_name,
                segment_duration_s,
            )

        # 3. Outro jingle
        outro = self._selector.get_outro_jingle()
        if outro:
            outro = outro.set_frame_rate(48000).set_channels(2).set_sample_width(2)
            outro = outro.fade_in(300).fade_out(200)
            if len(mixed) >= CROSSFADE_MS:
                mixed = mixed.append(
                    outro, crossfade=min(CROSSFADE_MS, len(outro) // 2)
                )
            else:
                mixed += outro
            logger.info("Added outro jingle: %.1fs", len(outro) / 1000.0)

        logger.info("Final mixed audio: %.1fs", len(mixed) / 1000.0)
        return mixed

    def _set_background_level(
        self,
        background: AudioSegment,
        speech: AudioSegment,
        target_db: float = BACKGROUND_DB_BELOW_SPEECH,
    ) -> AudioSegment:
        """Normalize background relative to speech RMS, targeting -18 to -24 dB below speech."""
        speech_rms = speech.rms
        bg_rms = background.rms
        if bg_rms == 0 or speech_rms == 0:
            return background

        current_diff = (
            20 * math.log10(bg_rms / speech_rms)
            if bg_rms > 0 and speech_rms > 0
            else 0
        )
        adjustment = target_db - current_diff
        return background + adjustment

    def _apply_ducking(
        self,
        background: AudioSegment,
        speech: AudioSegment,
        duck_db: float = DUCK_DB,
        pause_threshold_ms: int = PAUSE_THRESHOLD_MS,
        silence_thresh_dbfs: float = SILENCE_THRESH_DBFS,
    ) -> AudioSegment:
        """Reduce background volume during speech, restore during pauses > 1.5s."""
        # Detect silent regions in speech
        silent_ranges = detect_silence(
            speech,
            min_silence_len=pause_threshold_ms,
            silence_thresh=silence_thresh_dbfs,
        )

        if not silent_ranges:
            # No pauses detected — duck the entire background
            return background + duck_db

        # Build a ducked version
        ducked = AudioSegment.empty()
        prev_end = 0

        for silence_start, silence_end in silent_ranges:
            # Speech region (ducked)
            if silence_start > prev_end:
                speech_region = background[prev_end:silence_start]
                ducked += speech_region + duck_db
            # Pause region (full volume)
            pause_region = background[silence_start:silence_end]
            ducked += pause_region
            prev_end = silence_end

        # Remaining speech after last pause
        if prev_end < len(background):
            ducked += background[prev_end:] + duck_db

        return ducked

    def _estimate_segment_boundaries(
        self,
        speech: AudioSegment,
        movie_segments: list[str],
    ) -> list[tuple[int, int]]:
        """Estimate start/end ms for each movie segment.
        Divides speech duration evenly across segments."""
        n = max(len(movie_segments), 1)
        total_ms = len(speech)
        segment_ms = total_ms // n
        boundaries = []
        for i in range(n):
            start = i * segment_ms
            end = (i + 1) * segment_ms if i < n - 1 else total_ms
            boundaries.append((start, end))
        return boundaries

    def _loop_track(self, track: AudioSegment, target_ms: int) -> AudioSegment:
        """Loop a music track to fill the target duration, with fade at loop points."""
        if len(track) >= target_ms:
            return track[:target_ms].fade_out(FADE_MS)

        looped = AudioSegment.empty()
        while len(looped) < target_ms:
            chunk = track.fade_in(FADE_MS).fade_out(FADE_MS)
            looped += chunk

        return looped[:target_ms]
