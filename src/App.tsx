/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { 
  Play, Pause, RotateCcw, Search, ExternalLink, Loader2
} from 'lucide-react';
import { getDailyBriefing } from './lib/gemini';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * Converts raw PCM base64 data to a playable WAV Blob
 * Gemini TTS returns 24kHz, 16-bit, mono PCM
 */
function pcmToWav(base64Pcm: string): Blob {
  const binaryString = window.atob(base64Pcm);
  const len = binaryString.length;
  const bytes = new Uint8Array(len);
  for (let i = 0; i < len; i++) {
    bytes[i] = binaryString.charCodeAt(i);
  }

  const sampleRate = 24000;
  const numChannels = 1;
  const bitsPerSample = 16;
  
  const buffer = new ArrayBuffer(44 + bytes.length);
  const view = new DataView(buffer);

  /* RIFF identifier */
  view.setUint32(0, 0x52494646, false); // "RIFF"
  /* file length */
  view.setUint32(4, 36 + bytes.length, true);
  /* RIFF type */
  view.setUint32(8, 0x57415645, false); // "WAVE"
  /* format chunk identifier */
  view.setUint32(12, 0x666d7420, false); // "fmt "
  /* format chunk length */
  view.setUint32(16, 16, true);
  /* sample format (raw) */
  view.setUint16(20, 1, true);
  /* channel count */
  view.setUint16(22, numChannels, true);
  /* sample rate */
  view.setUint32(24, sampleRate, true);
  /* byte rate (sample rate * block align) */
  view.setUint32(28, sampleRate * numChannels * (bitsPerSample / 8), true);
  /* block align (channel count * bytes per sample) */
  view.setUint16(32, numChannels * (bitsPerSample / 8), true);
  /* bits per sample */
  view.setUint16(34, bitsPerSample, true);
  /* data chunk identifier */
  view.setUint32(36, 0x64617461, false); // "data"
  /* data chunk length */
  view.setUint32(40, bytes.length, true);

  // Write the PCM data efficiently
  new Uint8Array(buffer, 44).set(bytes);

  return new Blob([buffer], { type: 'audio/wav' });
}

export default function App() {
  const [briefing, setBriefing] = useState<{ script: string; audioBase64: string | null; sources: any[] } | null>(null);
  const [loadingBriefing, setLoadingBriefing] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [playbackRate, setPlaybackRate] = useState(1);
  const [showFullScript, setShowFullScript] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    handleRefreshBriefing();
  }, []);

  useEffect(() => {
    if (audioRef.current) {
      audioRef.current.playbackRate = playbackRate;
    }
  }, [audioUrl, playbackRate]);

  const handleRefreshBriefing = async () => {
    setLoadingBriefing(true);
    setIsPlaying(false);
    setCurrentTime(0);
    if (audioUrl) URL.revokeObjectURL(audioUrl);
    setAudioUrl(null);
    
    try {
      const data = await getDailyBriefing();
      setBriefing(data);
      if (data.audioBase64) {
        console.log("Audio data received, length:", data.audioBase64.length);
        const blob = pcmToWav(data.audioBase64);
        const url = URL.createObjectURL(blob);
        setAudioUrl(url);
      } else {
        console.error("No audio data received from Gemini");
      }
    } catch (error) {
      console.error("Briefing error:", error);
    } finally {
      setLoadingBriefing(false);
    }
  };

  const togglePlay = () => {
    if (!audioRef.current || !audioUrl) {
      console.warn("Audio not ready", { hasRef: !!audioRef.current, hasUrl: !!audioUrl });
      return;
    }
    if (isPlaying) {
      audioRef.current.pause();
    } else {
      const playPromise = audioRef.current.play();
      if (playPromise !== undefined) {
        playPromise.catch(error => {
          console.error("Playback failed:", error);
          setIsPlaying(false);
        });
      }
    }
  };

  const handleTimeUpdate = () => {
    if (audioRef.current) {
      setCurrentTime(audioRef.current.currentTime);
    }
  };

  const handleLoadedMetadata = () => {
    if (audioRef.current) {
      setDuration(audioRef.current.duration);
    }
  };

  const handleScrub = (e: React.ChangeEvent<HTMLInputElement>) => {
    const time = parseFloat(e.target.value);
    if (audioRef.current) {
      audioRef.current.currentTime = time;
      setCurrentTime(time);
    }
  };

  const handleSpeedChange = (rate: number) => {
    setPlaybackRate(rate);
    if (audioRef.current) {
      audioRef.current.playbackRate = rate;
    }
  };

  const formatTime = (time: number) => {
    const minutes = Math.floor(time / 60);
    const seconds = Math.floor(time % 60);
    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
  };

  const sentences = briefing?.script.split(/(?<=[.!?])\s+/) || [];
  const activeSentenceIndex = briefing && duration > 0 
    ? Math.min(Math.floor((currentTime / duration) * sentences.length), sentences.length - 1)
    : -1;

  const today = new Date().toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });

  return (
    <div className="min-h-screen relative overflow-hidden flex flex-col">
      <div className="atmosphere" />
      
      {/* Navigation */}
      <nav className="relative z-10 flex items-center justify-between px-4 md:px-8 py-6 border-b border-white/5">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-orange-500 rounded-full flex items-center justify-center shadow-lg shadow-orange-500/20">
            <Play className="w-5 h-5 fill-white text-white ml-1" />
          </div>
          <span className="font-sans text-2xl tracking-tight">Cinevox</span>
        </div>
        
        <div className="hidden lg:block">
          <span className="micro-label">{new Date().toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}</span>
        </div>
      </nav>

      {/* Main Content */}
      <main className="relative z-10 flex-1 container mx-auto px-4 md:px-6 py-8 md:py-12 max-w-6xl">
        <div className="grid lg:grid-cols-2 gap-8 lg:gap-12 items-start">
          <div className="space-y-6 md:space-y-8 lg:sticky lg:top-12">
            <div>
              <span className="micro-label text-orange-500 mb-3 md:mb-4 block">{today}</span>
              <h1 className="cinematic-title mb-4 md:mb-6">Welcome!</h1>
              <p className="text-white/60 text-base md:text-lg leading-relaxed max-w-md">
                A daily digest of the latest film reviews and news made for film enthusiasts.
              </p>
            </div>

            <div className="glass-panel p-5 md:p-8 space-y-5 md:space-y-6">
              <div className="flex flex-col gap-5">
                <div className="flex items-center gap-4">
                  <button 
                    onClick={togglePlay}
                    disabled={!audioUrl || loadingBriefing}
                    className="w-12 h-12 md:w-16 md:h-16 bg-white text-black rounded-full flex items-center justify-center hover:scale-105 transition-transform disabled:opacity-50 shrink-0"
                  >
                    {loadingBriefing ? (
                      <Loader2 className="w-6 h-6 md:w-8 md:h-8 animate-spin" />
                    ) : isPlaying ? (
                      <Pause className="w-6 h-6 md:w-8 md:h-8 fill-black" />
                    ) : (
                      <Play className="w-6 h-6 md:w-8 md:h-8 fill-black ml-1" />
                    )}
                  </button>
                  <div>
                    <h3 className="font-medium text-base md:text-lg">Episode 1</h3>
                    <p className="text-[10px] text-white/40 uppercase tracking-wider"></p>
                  </div>
                </div>

                <div className="flex items-center justify-between border-t border-white/5 pt-4">
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] text-white/40 uppercase font-mono mr-1">Speed</span>
                    <div className="flex bg-white/5 rounded-lg p-1">
                      {[1, 1.25, 1.5, 2].map((rate) => (
                        <button
                          key={rate}
                          onClick={() => handleSpeedChange(rate)}
                          className={cn(
                            "px-2 py-1 text-[10px] font-mono rounded transition-colors",
                            playbackRate === rate ? "bg-white text-black" : "text-white/40 hover:text-white"
                          )}
                        >
                          {rate}x
                        </button>
                      ))}
                    </div>
                  </div>
                  <button 
                    onClick={handleRefreshBriefing}
                    disabled={loadingBriefing}
                    className="p-2.5 rounded-full border border-white/10 hover:bg-white/5 transition-colors disabled:opacity-50"
                    title="Refresh Briefing"
                  >
                    <RotateCcw className={cn("w-4 h-4", loadingBriefing && "animate-spin")} />
                  </button>
                </div>
              </div>

              <div className="space-y-3">
                <div className="relative group">
                  <input 
                    type="range"
                    min="0"
                    max={duration || 0}
                    step="0.1"
                    value={currentTime}
                    onChange={handleScrub}
                    className="w-full h-1 bg-white/10 rounded-full appearance-none cursor-pointer accent-orange-500 group-hover:h-2 transition-all"
                  />
                </div>
                <div className="flex justify-between text-[10px] text-white/40 font-mono">
                  <span>{formatTime(currentTime)}</span>
                  <span>{formatTime(duration)}</span>
                </div>
              </div>

              {audioUrl && (
                <audio 
                  ref={audioRef} 
                  src={audioUrl} 
                  onTimeUpdate={handleTimeUpdate}
                  onLoadedMetadata={handleLoadedMetadata}
                  onEnded={() => setIsPlaying(false)}
                  onPause={() => setIsPlaying(false)}
                  onPlay={() => setIsPlaying(true)}
                  className="hidden"
                />
              )}
            </div>

            <div className="flex flex-wrap gap-3">
              {briefing?.sources.map((source: any, i: number) => (
                <a 
                  key={i}
                  href={source.web?.uri}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/5 border border-white/10 text-xs hover:bg-white/10 transition-colors"
                >
                  <Search className="w-3 h-3 text-orange-500" />
                  {source.web?.title || "Source"}
                  <ExternalLink className="w-3 h-3 opacity-40" />
                </a>
              ))}
            </div>
          </div>

          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold uppercase tracking-widest text-white/40">
                {showFullScript ? "Full Script" : "Follow Along"}
              </h2>
              <button 
                onClick={() => setShowFullScript(!showFullScript)}
                className="text-xs text-orange-500 hover:underline"
              >
                {showFullScript ? "Show Live Transcript" : "View Full Script"}
              </button>
            </div>

            <div className="glass-panel p-6 md:p-8 min-h-[300px] md:min-h-[400px] max-h-[500px] md:max-h-[600px] overflow-y-auto scrollbar-hide">
              <div className="space-y-4 md:space-y-6 font-serif text-lg md:text-xl leading-relaxed">
                {showFullScript ? (
                  <div className="text-white/80">
                    {briefing?.script}
                  </div>
                ) : (
                  sentences.map((sentence, i) => (
                    <motion.p
                      key={i}
                      animate={{ 
                        opacity: i === activeSentenceIndex ? 1 : 0.2,
                        scale: i === activeSentenceIndex ? 1.02 : 1,
                        color: i === activeSentenceIndex ? "#fff" : "rgba(255,255,255,0.4)"
                      }}
                      className={cn(
                        "transition-all duration-500",
                        i === activeSentenceIndex && "text-white"
                      )}
                    >
                      {sentence}
                    </motion.p>
                  ))
                )}
              </div>
            </div>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="relative z-10 px-4 md:px-8 py-6 border-t border-white/5 flex flex-col md:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-6">
          <span className="micro-label">© 2026 Cinevox</span>
        </div>

      </footer>
    </div>
  );
}
