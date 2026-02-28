# Gemini Prompts for Google AI Studio

These prompts are designed to be tested in [Google AI Studio](https://aistudio.google.com) before being integrated into the backend code.

## How to use
1. Open Google AI Studio
2. Select Gemini model (Gemini 1.5 Pro recommended)
3. Paste the system prompt from each file
4. Paste the sample input as the user message
5. Tweak temperature and parameters as noted
6. Once you're happy with the output, the backend code will use the same prompts

## Files
- `summarizer_prompt.md` — Review summarization (temp: 0.3)
- `sentiment_prompt.md` — Sentiment analysis (temp: 0.2)
- `script_generator_prompt.md` — Podcast narration script (temp: 0.7)
