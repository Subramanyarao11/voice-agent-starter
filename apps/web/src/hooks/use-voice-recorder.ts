import { useCallback } from "react";
import { useReactMediaRecorder, type StatusMessages } from "react-media-recorder";

const RECORDING_STATUSES: StatusMessages[] = ["acquiring_media", "recording", "stopping"];

export function useVoiceRecorder(onComplete: (audio: Blob) => void) {
  const handleStop = useCallback(
    (_blobUrl: string, blob: Blob) => {
      if (blob.size > 0) onComplete(blob);
    },
    [onComplete],
  );

  const recorder = useReactMediaRecorder({
    audio: true,
    video: false,
    stopStreamsOnStop: true,
    onStop: handleStop,
  });

  return {
    status: recorder.status,
    error: recorder.error,
    isRecording: RECORDING_STATUSES.includes(recorder.status),
    startRecording: recorder.startRecording,
    stopRecording: recorder.stopRecording,
  };
}
