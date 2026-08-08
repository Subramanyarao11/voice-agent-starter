import { useCallback, useEffect, useRef, useState } from "react";

import { turnResponseSchema, voiceStreamUrl, type TurnResponse } from "@/lib/api";

type StreamStatus = "idle" | "connecting" | "listening" | "processing" | "speaking";

type UseStreamingVoiceOptions = {
  accessToken: string;
  languageCode: string;
  stateCode: string;
  enabled: boolean;
  onTurn: (turn: TurnResponse) => void;
};

type QueuedAudio = {
  url: string;
};

const SILENCE_RMS_THRESHOLD = 0.018;
const SPEECH_START_MS = 220;
const SILENCE_END_MS = 850;
const MAX_RECORDING_MS = 90_000;

function supportedInBrowser(): boolean {
  return (
    typeof window !== "undefined" &&
    typeof WebSocket !== "undefined" &&
    typeof MediaRecorder !== "undefined" &&
    Boolean(navigator.mediaDevices?.getUserMedia)
  );
}

function supportedMimeType(): string {
  const candidates = ["audio/webm;codecs=opus", "audio/ogg;codecs=opus", "audio/webm"];
  return candidates.find((mimeType) => MediaRecorder.isTypeSupported(mimeType)) ?? "";
}

function base64ToUrl(value: string, mimeType: string): string {
  const binary = atob(value);
  const bytes = Uint8Array.from(binary, (character) => character.charCodeAt(0));
  return URL.createObjectURL(new Blob([bytes], { type: mimeType }));
}

export function useStreamingVoice({
  accessToken,
  languageCode,
  stateCode,
  enabled,
  onTurn,
}: UseStreamingVoiceOptions) {
  const [status, setStatus] = useState<StreamStatus>("idle");
  const [error, setError] = useState<string | null>(null);
  const socketRef = useRef<WebSocket | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const animationFrameRef = useRef<number | null>(null);
  const audioQueueRef = useRef<QueuedAudio[]>([]);
  const currentAudioRef = useRef<HTMLAudioElement | null>(null);
  const currentAudioUrlRef = useRef<string | null>(null);
  const recordingStartedAtRef = useRef(0);
  const speechStartedRef = useRef(false);
  const loudSinceRef = useRef<number | null>(null);
  const lastLoudAtRef = useRef(0);
  const stopRequestedRef = useRef(false);

  const isSupported = supportedInBrowser();

  const clearAudioQueue = useCallback(() => {
    for (const item of audioQueueRef.current) URL.revokeObjectURL(item.url);
    audioQueueRef.current = [];
    currentAudioRef.current?.pause();
    currentAudioRef.current = null;
    if (currentAudioUrlRef.current) URL.revokeObjectURL(currentAudioUrlRef.current);
    currentAudioUrlRef.current = null;
  }, []);

  const playNextRef = useRef<() => void>(() => undefined);
  const playAudio = useCallback(() => {
    if (currentAudioRef.current) return;
    const item = audioQueueRef.current.shift();
    if (!item) return;

    const audio = new Audio(item.url);
    currentAudioRef.current = audio;
    currentAudioUrlRef.current = item.url;
    audio.onended = () => {
      URL.revokeObjectURL(item.url);
      currentAudioRef.current = null;
      currentAudioUrlRef.current = null;
      playNextRef.current();
    };
    audio.onerror = () => {
      URL.revokeObjectURL(item.url);
      currentAudioRef.current = null;
      currentAudioUrlRef.current = null;
      playNextRef.current();
    };
    void audio.play().catch(() => {
      URL.revokeObjectURL(item.url);
      currentAudioRef.current = null;
      currentAudioUrlRef.current = null;
      for (const queued of audioQueueRef.current) URL.revokeObjectURL(queued.url);
      audioQueueRef.current = [];
      setError("Voice reply is ready, but the browser blocked automatic playback. The text answer is still available.");
    });
  }, []);
  playNextRef.current = playAudio;

  const stopAnalyser = useCallback(() => {
    if (animationFrameRef.current !== null) cancelAnimationFrame(animationFrameRef.current);
    animationFrameRef.current = null;
    audioContextRef.current?.close().catch(() => undefined);
    audioContextRef.current = null;
  }, []);

  const stopMedia = useCallback(() => {
    stopAnalyser();
    for (const track of streamRef.current?.getTracks() ?? []) track.stop();
    streamRef.current = null;
    recorderRef.current = null;
  }, [stopAnalyser]);

  const interrupt = useCallback(() => {
    stopRequestedRef.current = true;
    const socket = socketRef.current;
    if (socket?.readyState === WebSocket.OPEN) socket.send(JSON.stringify({ type: "interrupt" }));
    socket?.close(1000, "interrupted");
    socketRef.current = null;
    stopMedia();
    clearAudioQueue();
    setStatus("idle");
  }, [clearAudioQueue, stopMedia]);

  const finishRecording = useCallback(() => {
    stopRequestedRef.current = true;
    const recorder = recorderRef.current;
    if (!recorder || recorder.state === "inactive") return;
    recorder.stop();
  }, []);

  const startVad = useCallback(
    (stream: MediaStream, onSilence: () => void) => {
      if (typeof AudioContext === "undefined") return;
      const context = new AudioContext();
      void context.resume();
      const source = context.createMediaStreamSource(stream);
      const analyser = context.createAnalyser();
      analyser.fftSize = 1024;
      source.connect(analyser);
      audioContextRef.current = context;
      const samples = new Float32Array(analyser.fftSize);

      const sample = () => {
        analyser.getFloatTimeDomainData(samples);
        const rms = Math.sqrt(samples.reduce((sum, value) => sum + value * value, 0) / samples.length);
        const now = performance.now();
        if (rms >= SILENCE_RMS_THRESHOLD) {
          loudSinceRef.current ??= now;
          lastLoudAtRef.current = now;
          if (!speechStartedRef.current && now - loudSinceRef.current >= SPEECH_START_MS) {
            speechStartedRef.current = true;
          }
        } else if (speechStartedRef.current && now - lastLoudAtRef.current >= SILENCE_END_MS) {
          onSilence();
          return;
        }
        if (now - recordingStartedAtRef.current >= MAX_RECORDING_MS) {
          onSilence();
          return;
        }
        animationFrameRef.current = requestAnimationFrame(sample);
      };
      animationFrameRef.current = requestAnimationFrame(sample);
    },
    [],
  );

  const start = useCallback(async () => {
    if (!enabled || !accessToken || !isSupported) return;
    if (status !== "idle") interrupt();
    setError(null);
    clearAudioQueue();
    const mimeType = supportedMimeType();
    if (!mimeType) {
      setError("This browser cannot create a compatible voice recording.");
      return;
    }

    const socket = new WebSocket(voiceStreamUrl());
    socketRef.current = socket;
    setStatus("connecting");
    stopRequestedRef.current = false;
    speechStartedRef.current = false;
    loudSinceRef.current = null;
    lastLoudAtRef.current = performance.now();

    socket.onopen = async () => {
      try {
        socket.send(JSON.stringify({
          type: "start",
          access_token: accessToken,
          language_code: languageCode,
          state_code: stateCode,
          mime_type: mimeType,
          speak: true,
        }));
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
        });
        if (socketRef.current !== socket || socket.readyState !== WebSocket.OPEN) {
          for (const track of stream.getTracks()) track.stop();
          return;
        }
        streamRef.current = stream;
        const recorder = new MediaRecorder(stream, { mimeType });
        recorderRef.current = recorder;
        recorder.ondataavailable = (event) => {
          if (event.data.size > 0 && socket.readyState === WebSocket.OPEN) socket.send(event.data);
        };
        recorder.onstop = () => {
          stopMedia();
          if (socket.readyState === WebSocket.OPEN && stopRequestedRef.current) {
            socket.send(JSON.stringify({ type: "end_turn" }));
            setStatus("processing");
          }
        };
        recorder.onerror = () => {
          setError("The browser could not continue recording. Please try again.");
          socket.close();
        };
        recordingStartedAtRef.current = performance.now();
        recorder.start(250);
        startVad(stream, finishRecording);
        setStatus("listening");
      } catch {
        setError("Microphone access is unavailable. Check the browser permission and try again.");
        socket.close();
        stopMedia();
        setStatus("idle");
      }
    };

    socket.onmessage = (event) => {
      if (typeof event.data !== "string") return;
      let payload: unknown;
      try {
        payload = JSON.parse(event.data);
      } catch {
        setError("The voice connection returned an invalid event.");
        return;
      }
      if (!payload || typeof payload !== "object" || !("type" in payload)) return;
      if (socketRef.current !== socket) return;
      const message = payload as { type: string; [key: string]: unknown };
      if (message.type === "transcript") {
        setStatus("processing");
      } else if (message.type === "turn") {
        const parsed = turnResponseSchema.safeParse(message.turn);
        if (parsed.success) onTurn(parsed.data);
      } else if (message.type === "audio_chunk" && typeof message.audio_base64 === "string") {
        const mime = typeof message.mime_type === "string" ? message.mime_type : "audio/wav";
        audioQueueRef.current.push({ url: base64ToUrl(message.audio_base64, mime) });
        setStatus("speaking");
        playNextRef.current();
      } else if (message.type === "tts_error") {
        setError("Text is ready, but one voice sentence could not be played.");
      } else if (message.type === "error" && typeof message.message === "string") {
        setError(message.message);
        setStatus("idle");
      } else if (message.type === "turn_end") {
        setStatus("idle");
        socket.close(1000, "turn-complete");
      }
    };

    socket.onerror = () => {
      if (socketRef.current !== socket) return;
      setError("The streaming voice connection failed. Text chat is still available.");
      setStatus("idle");
    };
    socket.onclose = () => {
      if (socketRef.current !== socket) return;
      socketRef.current = null;
      stopMedia();
      if (status !== "speaking" && status !== "processing") setStatus("idle");
    };
  }, [
    accessToken,
    clearAudioQueue,
    enabled,
    finishRecording,
    isSupported,
    languageCode,
    onTurn,
    interrupt,
    startVad,
    stateCode,
    status,
    stopMedia,
  ]);

  const stop = useCallback(() => {
    if (status === "connecting") {
      interrupt();
    } else if (status === "listening") {
      finishRecording();
    }
  }, [finishRecording, interrupt, status]);

  useEffect(() => () => {
    socketRef.current?.close();
    stopMedia();
    clearAudioQueue();
  }, [clearAudioQueue, stopMedia]);

  return {
    supported: isSupported,
    status,
    error,
    isListening: status === "connecting" || status === "listening",
    isBusy: status !== "idle",
    start,
    stop,
    interrupt,
  };
}
