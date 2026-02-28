import { GoogleGenAI, Modality, Type, GenerateContentResponse } from "@google/genai";

// Initialize with the environment key for free models
const getAI = (useUserKey: boolean = false) => {
  const apiKey = useUserKey ? process.env.API_KEY : process.env.GEMINI_API_KEY;
  return new GoogleGenAI({ apiKey: apiKey || process.env.GEMINI_API_KEY || "" });
};

export async function getDailyBriefing() {
  const ai = getAI(false); // Free model
  const today = new Date().toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });
  
  // 1. Search for latest film news and top reviews
  const searchResponse = await ai.models.generateContent({
    model: "gemini-3-flash-preview",
    contents: `Find the top 3 film reviews from major publications (like Variety, Hollywood Reporter, IndieWire) and the top 3 breaking news stories in the film industry from the last 24 hours. 
    
    Summarize them into a cohesive, engaging 2-minute podcast script for film enthusiasts.
    
    CRITICAL INSTRUCTIONS:
    1. Start the script EXACTLY with: "This is Film Digest and today is ${today}. Here's the latest on what's happening in the film world."
    2. For every movie mentioned, provide a quick one-liner description of what the movie is about.
    3. Keep the tone professional and concise.`,
    config: {
      tools: [{ googleSearch: {} }],
    },
  });

  const script = searchResponse.text || `This is Film Digest and today is ${today}. Here's the latest on what's happening in the film world. Today we're looking at the latest in film...`;

  // 2. Generate TTS for the script
  const ttsResponse = await ai.models.generateContent({
    model: "gemini-2.5-flash-preview-tts",
    contents: [{ parts: [{ text: `Say in a professional narrator voice: ${script}` }] }],
    config: {
      responseModalities: [Modality.AUDIO],
      speechConfig: {
        voiceConfig: {
          prebuiltVoiceConfig: { voiceName: 'Zephyr' },
        },
      },
    },
  });

  let audioBase64 = null;
  const parts = ttsResponse.candidates?.[0]?.content?.parts || [];
  for (const part of parts) {
    if (part.inlineData?.data) {
      audioBase64 = part.inlineData.data;
      break;
    }
  }
  
  return {
    script,
    audioBase64,
    sources: searchResponse.candidates?.[0]?.groundingMetadata?.groundingChunks || []
  };
}
