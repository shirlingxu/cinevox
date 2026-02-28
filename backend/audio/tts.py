"""Audio Generator — converts narration scripts to natural speech using Gemini TTS.

Uses Gemini 2.5 Flash Preview TTS with multi-speaker support for a
two-host podcast feel. Outputs MP3 files to data/episodes/.
"""

import io
import logging
import re
import uuid
import wave
from pathlib import Path

from google import genai
from google.genai import types
from pydub import AudioSegment

from backend.config import get_gemini_api_key
from backend.models import NarrationScript

logger = logging.getLogger(__name__)

EPISODES_DIR = Path("data/episodes")
TTS_MODEL = "gemini-2.5-flash-preview-tts"

# Gemini TTS outputs raw PCM: 24kHz, 16-bit, mono
PCM_RATE = 24000
PCM_SAMPLE_WIDTH = 2
PCM_CHANNELS = 1

# Max chars per TTS request (model has 32k token context window, ~8k chars is safe)
CHUNK_MAX_CHARS = 6000


# Director's notes for the TTS model — sets the podcast vibe
ALEX_SCENE = """# AUDIO PROFILE: Alex
## CineVox Lead Host

### DIRECTOR'S NOTES
Style: Confident, witty film podcast host. Warm baritone energy. Think of a knowledgeable friend who genuinely loves movies and gets excited sharing opinions. Natural laughs and reactions.
Pacing: Conversational and dynamic — speeds up when excited about a film, slows down for dramatic emphasis. Natural breathing pauses.
Accent: Standard American English, casual and approachable.
"""

MAYA_SCENE = """# AUDIO PROFILE: Maya
## CineVox Co-Host

### DIRECTOR'S NOTES
Style: Thoughtful, analytical co-host with a warm personality. Brings sharp observations and occasionally playful sarcasm. Genuine reactions — laughs, surprised sounds, agreement hums.
Pacing: Measured but engaging — takes a beat before making a point, then delivers with conviction. Natural conversational rhythm.
Accent: Standard American English, bright and clear.
"""


class AudioGenerator:
    """Converts narration scripts to natural podcast audio via Gemini TTS."""

    def __init__(self, output_dir: Path | None = None):
        self._output_dir = output_dir or EPISODES_DIR
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._client = genai.Client(api_key=get_gemini_api_key())

    def _clean_script(self, text: str) -> str:
        """Remove [PAUSE], [TRANSITION], [EMPHASIS] cues — Gemini TTS handles pacing natively."""
        text = re.sub(r'\[PAUSE\]', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\[TRANSITION\]', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\[EMPHASIS\]', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\[.*?\]', '', text)
        return text.strip()

    def _is_multi_speaker(self, text: str) -> bool:
        """Check if script has Alex/Maya dialogue format."""
        return bool(re.search(r'^(Alex|Maya):', text, re.MULTILINE))

    def _chunk_script(self, text: str) -> list[str]:
        """Split long scripts into chunks that fit the TTS context window.

        Splits at paragraph boundaries to keep dialogue pairs together.
        """
        if len(text) <= CHUNK_MAX_CHARS:
            return [text]

        chunks = []
        lines = text.split('\n')
        current_chunk = []
        current_len = 0

        for line in lines:
            line_len = len(line) + 1  # +1 for newline
            if current_len + line_len > CHUNK_MAX_CHARS and current_chunk:
                chunks.append('\n'.join(current_chunk))
                current_chunk = []
                current_len = 0
            current_chunk.append(line)
            current_len += line_len

        if current_chunk:
            chunks.append('\n'.join(current_chunk))

        return chunks

    def _pcm_to_audio_segment(self, pcm_data: bytes) -> AudioSegment:
        """Convert raw PCM bytes from Gemini TTS to a pydub AudioSegment."""
        return AudioSegment(
            data=pcm_data,
            sample_width=PCM_SAMPLE_WIDTH,
            frame_rate=PCM_RATE,
            channels=PCM_CHANNELS,
        )

    def _generate_multi_speaker(self, text: str) -> bytes:
        """Generate multi-speaker audio using Gemini TTS."""
        prompt = f"{ALEX_SCENE}\n{MAYA_SCENE}\n\n#### TRANSCRIPT\n{text}"

        response = self._client.models.generate_content(
            model=TTS_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    multi_speaker_voice_config=types.MultiSpeakerVoiceConfig(
                        speaker_voice_configs=[
                            types.SpeakerVoiceConfig(
                                speaker="Alex",
                                voice_config=types.VoiceConfig(
                                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                        voice_name="Orus",  # Firm, confident
                                    )
                                ),
                            ),
                            types.SpeakerVoiceConfig(
                                speaker="Maya",
                                voice_config=types.VoiceConfig(
                                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                        voice_name="Aoede",  # Breezy, bright
                                    )
                                ),
                            ),
                        ]
                    )
                ),
            ),
        )
        return response.candidates[0].content.parts[0].inline_data.data

    def _generate_single_speaker(self, text: str) -> bytes:
        """Generate single-speaker audio using Gemini TTS (fallback)."""
        prompt = f"""# AUDIO PROFILE: CineVox Host
### DIRECTOR'S NOTES
Style: Warm, engaging podcast host. Conversational and natural, like talking to a friend about movies.
Pacing: Dynamic — varies naturally with the content. Pauses for emphasis.
Accent: Standard American English.

#### TRANSCRIPT
{text}"""

        response = self._client.models.generate_content(
            model=TTS_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name="Orus",
                        )
                    )
                ),
            ),
        )
        return response.candidates[0].content.parts[0].inline_data.data

    def generate(self, script: NarrationScript, podcast_id: str | None = None, max_retries: int = 2) -> str:
        """Convert script to MP3 using Gemini TTS. Returns the file path."""
        cleaned = self._clean_script(script.text)
        if not cleaned:
            raise ValueError("Script produced no speakable content")

        multi_speaker = self._is_multi_speaker(cleaned)
        chunks = self._chunk_script(cleaned)
        pid = podcast_id or str(uuid.uuid4())[:8]
        output_path = self._output_dir / f"{pid}.mp3"

        for attempt in range(max_retries + 1):
            try:
                combined = AudioSegment.empty()

                for i, chunk in enumerate(chunks):
                    logger.info(
                        "TTS chunk %d/%d (%d chars, %s)",
                        i + 1, len(chunks), len(chunk),
                        "multi" if multi_speaker else "single",
                    )
                    if multi_speaker:
                        pcm_data = self._generate_multi_speaker(chunk)
                    else:
                        pcm_data = self._generate_single_speaker(chunk)

                    segment = self._pcm_to_audio_segment(pcm_data)
                    combined += segment

                # Export final MP3
                combined.export(str(output_path), format="mp3")
                duration_seconds = len(combined) / 1000.0

                logger.info(
                    "Generated audio: %s (%.1fs, %d chunks)",
                    output_path, duration_seconds, len(chunks),
                )
                return str(output_path)

            except Exception as exc:
                logger.error(
                    "AudioGenerator attempt %d/%d failed: %s",
                    attempt + 1, max_retries + 1, exc,
                )
                if attempt >= max_retries:
                    raise

        raise RuntimeError("AudioGenerator exhausted retries")
