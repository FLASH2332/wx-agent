import React, { useEffect, useRef, useState } from 'react';
import { Play, Pause, Volume2 } from 'lucide-react';

export default function AudioPlayer({ audioBase64, autoPlay = true }) {
  const audioRef = useRef(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [hasAudio, setHasAudio] = useState(false);

  useEffect(() => {
    if (audioBase64) {
      const src = `data:audio/mp3;base64,${audioBase64}`;
      if (audioRef.current) {
        audioRef.current.src = src;
        setHasAudio(true);
        if (autoPlay) {
          audioRef.current.play().catch(e => console.error("Autoplay failed:", e));
        }
      }
    } else {
      setHasAudio(false);
    }
  }, [audioBase64, autoPlay]);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;

    const handlePlay = () => setIsPlaying(true);
    const handlePause = () => setIsPlaying(false);
    const handleEnded = () => setIsPlaying(false);

    audio.addEventListener('play', handlePlay);
    audio.addEventListener('pause', handlePause);
    audio.addEventListener('ended', handleEnded);

    return () => {
      audio.removeEventListener('play', handlePlay);
      audio.removeEventListener('pause', handlePause);
      audio.removeEventListener('ended', handleEnded);
    };
  }, []);

  const togglePlay = () => {
    if (!audioRef.current) return;
    if (isPlaying) {
      audioRef.current.pause();
    } else {
      audioRef.current.play();
    }
  };

  if (!hasAudio) return <audio ref={audioRef} className="hidden" />;

  return (
    <div className="flex items-center gap-3 p-2 px-4 rounded-full 
      bg-white/[0.04] border border-white/[0.06] mb-4 self-center w-full max-w-[200px] 
      shadow-[0_1px_3px_rgba(0,0,0,0.12),0_4px_12px_rgba(0,0,0,0.08)]
      backdrop-blur-xl">
      {/* Play/Pause — optical alignment: Play icon nudged 1px right */}
      <button 
        onClick={togglePlay}
        className="w-8 h-8 min-w-[32px] rounded-full bg-white/[0.08] hover:bg-white/[0.14] 
          flex items-center justify-center 
          transition-[background-color,transform] duration-150 press-scale
          shrink-0 text-white"
        aria-label={isPlaying ? "Pause audio" : "Play audio"}
      >
        {isPlaying 
          ? <Pause className="w-3.5 h-3.5" strokeWidth={2} /> 
          : <Play className="w-3.5 h-3.5 ml-[1px]" strokeWidth={2} />}
      </button>
      
      {/* Visualizer bars */}
      <div className="flex-1 flex items-center gap-[3px] h-4 overflow-hidden">
        {[1, 2, 3, 4, 5, 6, 7].map((i) => (
          <div 
            key={i}
            className={`w-[5px] bg-blue-400/80 rounded-full 
              transition-[height,opacity] duration-150
              ${isPlaying ? 'animate-pulse' : 'h-1 opacity-40'}`}
            style={{ 
              height: isPlaying ? `${20 + Math.random() * 80}%` : '4px',
              animationDelay: `${i * 0.1}s` 
            }}
          />
        ))}
      </div>
      
      <Volume2 
        className={`w-4 h-4 transition-[color] duration-150 
          ${isPlaying ? 'text-blue-400/80' : 'text-white/35'}`} 
        strokeWidth={1.5}
      />
      
      <audio ref={audioRef} className="hidden" />
    </div>
  );
}
