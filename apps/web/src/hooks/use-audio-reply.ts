import { useEffect, useRef, useState } from "react";

export function useAudioReply(source: string | null) {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [autoplayBlocked, setAutoplayBlocked] = useState(false);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio || !source) return;

    audio.load();
    void audio.play().catch(() => setAutoplayBlocked(true));
    return () => audio.pause();
  }, [source]);

  return { audioRef, autoplayBlocked };
}
