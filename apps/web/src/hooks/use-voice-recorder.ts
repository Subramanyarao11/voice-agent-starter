import { useCallback, useEffect, useRef, useState } from "react";

type RecorderStatus = "idle" | "acquiring_media" | "recording" | "stopping";

function supportedMimeType(): string | undefined {
  if (typeof MediaRecorder === "undefined") return undefined;
  return ["audio/webm;codecs=opus", "audio/ogg;codecs=opus", "audio/webm"].find((mimeType) =>
    MediaRecorder.isTypeSupported(mimeType),
  );
}

export function useVoiceRecorder(onComplete: (audio: Blob) => void) {
  const [status, setStatus] = useState<RecorderStatus>("idle");
  const [error, setError] = useState<string | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const acquiringRef = useRef(false);
  const onCompleteRef = useRef(onComplete);

  useEffect(() => {
    onCompleteRef.current = onComplete;
  }, [onComplete]);

  const releaseStream = useCallback(() => {
    for (const track of streamRef.current?.getTracks() ?? []) track.stop();
    streamRef.current = null;
  }, []);

  const startRecording = useCallback(() => {
    if (recorderRef.current || acquiringRef.current) return;
    if (typeof MediaRecorder === "undefined" || !navigator.mediaDevices?.getUserMedia) {
      setError("This browser cannot record audio. You can still type your request instead.");
      return;
    }

    acquiringRef.current = true;
    setError(null);
    setStatus("acquiring_media");

    void navigator.mediaDevices
      .getUserMedia({ audio: true })
      .then((stream) => {
        acquiringRef.current = false;
        streamRef.current = stream;
        chunksRef.current = [];

        const mimeType = supportedMimeType();
        const recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
        recorderRef.current = recorder;
        recorder.ondataavailable = (event) => {
          if (event.data.size > 0) chunksRef.current.push(event.data);
        };
        recorder.onerror = () => {
          setError("The browser could not record that audio. Please try again or type your request.");
          recorderRef.current = null;
          chunksRef.current = [];
          releaseStream();
          setStatus("idle");
        };
        recorder.onstop = () => {
          const audio = new Blob(chunksRef.current, { type: recorder.mimeType || mimeType || "audio/webm" });
          recorderRef.current = null;
          chunksRef.current = [];
          releaseStream();
          setStatus("idle");
          if (audio.size > 0) onCompleteRef.current(audio);
        };
        recorder.start();
        setStatus("recording");
      })
      .catch(() => {
        acquiringRef.current = false;
        releaseStream();
        setError("Microphone access was not available. Check browser permission or type your request instead.");
        setStatus("idle");
      });
  }, [releaseStream]);

  const stopRecording = useCallback(() => {
    const recorder = recorderRef.current;
    if (!recorder || recorder.state === "inactive") return;
    setStatus("stopping");
    recorder.stop();
  }, []);

  useEffect(() => {
    return () => {
      recorderRef.current?.stop();
      releaseStream();
    };
  }, [releaseStream]);

  return {
    status,
    error,
    isRecording: status === "acquiring_media" || status === "recording" || status === "stopping",
    startRecording,
    stopRecording,
  };
}
