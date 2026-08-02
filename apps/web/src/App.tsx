import { FormEvent, useEffect, useMemo, useRef, useState } from "react";

import {
  ApiError,
  Coverage,
  getCoverage,
  getHealth,
  getLanguages,
  getStates,
  Health,
  Language,
  resetSession,
  sendTextTurn,
  sendVoiceTurn,
  State,
  TurnResponse,
} from "./api";

type MessageRole = "caller" | "agent";

type Message = {
  id: string;
  role: MessageRole;
  text: string;
};

const CALLER_STORAGE_KEY = "sahaayak.caller_id";
const PREFERRED_LANGUAGE = "kn";
const PREFERRED_STATE = "KA";

function newCallerId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return `web_${crypto.randomUUID()}`;
  }
  return `web_${Date.now().toString(36)}_${Math.random().toString(36).slice(2)}`;
}

function getOrCreateCallerId(): string {
  const existing = window.localStorage.getItem(CALLER_STORAGE_KEY);
  if (existing) return existing;
  const created = newCallerId();
  window.localStorage.setItem(CALLER_STORAGE_KEY, created);
  return created;
}

function messageId(): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random()}`;
}

function labelForSlot(slot: string | null | undefined): string {
  if (!slot) return "none";
  return slot.replaceAll("_", " ");
}

function friendlyError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 503) {
      return "Voice is not configured on the API yet. Text chat is still available.";
    }
    return error.message;
  }
  if (error instanceof TypeError) {
    return "Could not reach the API. Start it with `make api`, then reload this page.";
  }
  return error instanceof Error ? error.message : "Something went wrong. Please try again.";
}

function preferredValue<T extends { code: string }>(items: T[], preferred: string): string {
  return items.some((item) => item.code === preferred) ? preferred : items[0]?.code ?? "";
}

function chooseMimeType(): string | undefined {
  if (typeof MediaRecorder === "undefined") return undefined;
  const choices = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus", "audio/mp4"];
  return choices.find((type) => MediaRecorder.isTypeSupported(type));
}

function App() {
  const [callerId] = useState(getOrCreateCallerId);
  const [languages, setLanguages] = useState<Language[]>([]);
  const [states, setStates] = useState<State[]>([]);
  const [coverage, setCoverage] = useState<Coverage | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [languageCode, setLanguageCode] = useState(PREFERRED_LANGUAGE);
  const [stateCode, setStateCode] = useState(PREFERRED_STATE);
  const [messages, setMessages] = useState<Message[]>([]);
  const [lastTurn, setLastTurn] = useState<TurnResponse | null>(null);
  const [draft, setDraft] = useState("");
  const [loadingCatalog, setLoadingCatalog] = useState(true);
  const [sending, setSending] = useState(false);
  const [recording, setRecording] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const activeLanguages = useMemo(
    () => languages.filter((language) => language.is_active),
    [languages],
  );
  const activeStates = useMemo(() => states.filter((state) => state.is_active), [states]);
  const selectedLanguage = activeLanguages.find((language) => language.code === languageCode);
  const selectedState = activeStates.find((state) => state.code === stateCode);
  const audioUrl =
    lastTurn?.audio_base64 && lastTurn.audio_mime_type
      ? `data:${lastTurn.audio_mime_type};base64,${lastTurn.audio_base64}`
      : null;
  const stateCoverage =
    (coverage?.by_state[stateCode] ?? 0) + (coverage?.by_state.central ?? 0);
  const voiceInputAvailable = health?.speech_to_text ?? true;

  useEffect(() => {
    let cancelled = false;
    async function loadCatalog() {
      setLoadingCatalog(true);
      try {
        const [languageRows, stateRows, coverageRow, healthRow] = await Promise.all([
          getLanguages(),
          getStates(),
          getCoverage(),
          getHealth(),
        ]);
        if (cancelled) return;
        setLanguages(languageRows);
        setStates(stateRows);
        setCoverage(coverageRow);
        setHealth(healthRow);
        const nextLanguages = languageRows.filter((language) => language.is_active);
        const nextStates = stateRows.filter((state) => state.is_active);
        setLanguageCode((current) => preferredValue(nextLanguages, current || PREFERRED_LANGUAGE));
        setStateCode((current) => preferredValue(nextStates, current || PREFERRED_STATE));
      } catch (loadError) {
        if (!cancelled) setError(friendlyError(loadError));
      } finally {
        if (!cancelled) setLoadingCatalog(false);
      }
    }
    void loadCatalog();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    return () => {
      streamRef.current?.getTracks().forEach((track) => track.stop());
      audioRef.current?.pause();
    };
  }, []);

  function recordTurn(callerText: string, response: TurnResponse) {
    setMessages((current) => [
      ...current,
      { id: messageId(), role: "caller", text: callerText },
      { id: messageId(), role: "agent", text: response.response_text },
    ]);
    setLastTurn(response);
  }

  async function submitText(event?: FormEvent) {
    event?.preventDefault();
    const text = draft.trim();
    if (!text || sending || !languageCode || !stateCode) return;
    setDraft("");
    setSending(true);
    setError(null);
    setNotice(null);
    try {
      const response = await sendTextTurn({
        caller_id: callerId,
        text,
        language_code: languageCode,
        state_code: stateCode,
      });
      recordTurn(text, response);
    } catch (requestError) {
      setDraft(text);
      setError(friendlyError(requestError));
    } finally {
      setSending(false);
    }
  }

  async function submitVoice(audio: Blob) {
    setSending(true);
    setError(null);
    setNotice(null);
    try {
      const response = await sendVoiceTurn(audio, {
        caller_id: callerId,
        language_code: languageCode,
        state_code: stateCode,
        speak: true,
      });
      recordTurn(response.transcript || "Voice turn", response);
    } catch (requestError) {
      setError(friendlyError(requestError));
    } finally {
      setSending(false);
    }
  }

  async function toggleRecording() {
    if (recording) {
      recorderRef.current?.stop();
      setRecording(false);
      return;
    }
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      setError("This browser does not support microphone recording. Text chat is still available.");
      return;
    }
    if (sending || !languageCode || !stateCode) return;

    try {
      setError(null);
      setNotice(null);
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      chunksRef.current = [];
      const mimeType = chooseMimeType();
      const recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
      recorderRef.current = recorder;
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) chunksRef.current.push(event.data);
      };
      recorder.onstop = () => {
        stream.getTracks().forEach((track) => track.stop());
        streamRef.current = null;
        recorderRef.current = null;
        const audio = new Blob(chunksRef.current, { type: recorder.mimeType || "audio/webm" });
        chunksRef.current = [];
        if (audio.size > 0) void submitVoice(audio);
      };
      recorder.start();
      setRecording(true);
    } catch (recordingError) {
      streamRef.current?.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
      setError(
        recordingError instanceof DOMException && recordingError.name === "NotAllowedError"
          ? "Microphone permission was denied. You can continue with text chat."
          : friendlyError(recordingError),
      );
    }
  }

  async function handleReset() {
    if (resetting || sending) return;
    setResetting(true);
    setError(null);
    setNotice(null);
    try {
      await resetSession(callerId);
      setMessages([]);
      setLastTurn(null);
      setDraft("");
      setNotice("Session cleared. Your next turn starts a fresh conversation.");
    } catch (resetError) {
      setError(friendlyError(resetError));
    } finally {
      setResetting(false);
    }
  }

  const disabled = loadingCatalog || sending || !languageCode || !stateCode;

  return (
    <main className="app-shell">
      <div className="ambient ambient-one" />
      <div className="ambient ambient-two" />

      <section className="topbar" aria-label="Sahaayak status">
        <a className="brand" href="/" aria-label="Sahaayak home">
          <span className="brand-mark">स</span>
          <span>
            <strong>Sahaayak</strong>
            <small>help, in your language</small>
          </span>
        </a>
        <div className="topbar-right">
          <span className="live-dot" />
          <span>{health?.status === "ok" ? "API connected" : "Connecting to API"}</span>
          <span className="caller-chip" title={callerId}>
            caller · {callerId.slice(-8)}
          </span>
        </div>
      </section>

      <section className="hero-grid">
        <div className="intro-column">
          <p className="eyebrow">A calmer way to find out</p>
          <h1>
            Find the help
            <br />
            meant for <em>you.</em>
          </h1>
          <p className="intro-copy">
            Speak or type what you need. Sahaayak asks only the questions that change your
            answer, then explains what it found.
          </p>

          <div className="signal-row">
            <span className="signal-icon">↗</span>
            <span>
              <strong>{coverage?.total ?? "—"}</strong> benefits loaded
              <small>coverage is shown honestly for this demo</small>
            </span>
          </div>

          <div className="promise-list" aria-label="What Sahaayak can do">
            <span>
              <b>01</b> schemes
            </span>
            <span>
              <b>02</b> scholarships
            </span>
            <span>
              <b>03</b> light job discovery
            </span>
          </div>
        </div>

        <div className="workspace-column">
          <div className="control-strip">
            <label>
              <span>Language</span>
              <select
                value={languageCode}
                onChange={(event) => setLanguageCode(event.target.value)}
                disabled={loadingCatalog || activeLanguages.length === 0}
              >
                {activeLanguages.map((language) => (
                  <option value={language.code} key={language.code}>
                    {language.native_name} · {language.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span>State</span>
              <select
                value={stateCode}
                onChange={(event) => setStateCode(event.target.value)}
                disabled={loadingCatalog || activeStates.length === 0}
              >
                {activeStates.map((state) => (
                  <option value={state.code} key={state.code}>
                    {state.name}
                  </option>
                ))}
              </select>
            </label>
            <div className="coverage-chip" title="Benefits in the selected state plus central schemes">
              <span className="coverage-pip" />
              <span>
                <b>{stateCoverage}</b> in {selectedState?.name ?? stateCode}
              </span>
            </div>
          </div>

          <div className="conversation-frame">
            <div className="conversation-header">
              <div>
                <span className="section-kicker">Your conversation</span>
                <h2>Tell me what you’re looking for.</h2>
              </div>
              <button className="reset-button" onClick={() => void handleReset()} disabled={resetting || sending}>
                {resetting ? "Clearing…" : "Reset session"}
              </button>
            </div>

            <div className="message-list" aria-live="polite">
              {messages.length === 0 ? (
                <div className="empty-conversation">
                  <span className="empty-orbit">✦</span>
                  <p>Start with something simple, like:</p>
                  <button onClick={() => setDraft("I need a scholarship")}>“I need a scholarship”</button>
                  <button onClick={() => setDraft("Tell me about government schemes")}>“Tell me about government schemes”</button>
                </div>
              ) : (
                messages.map((message) => (
                  <div className={`message-row ${message.role}`} key={message.id}>
                    <span className="message-label">{message.role === "caller" ? "you" : "sahaayak"}</span>
                    <p>{message.text}</p>
                  </div>
                ))
              )}
              {sending && (
                <div className="message-row agent thinking">
                  <span className="message-label">sahaayak</span>
                  <p>
                    <i /> <i /> <i />
                  </p>
                </div>
              )}
            </div>

            {audioUrl && (
              <div className="audio-reply">
                <span>Last answer</span>
                <audio ref={audioRef} controls autoPlay src={audioUrl}>
                  Your browser cannot play this answer.
                </audio>
              </div>
            )}

            <form className="composer" onSubmit={(event) => void submitText(event)}>
              <textarea
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && !event.shiftKey) {
                    event.preventDefault();
                    void submitText();
                  }
                }}
                placeholder={
                  selectedLanguage
                    ? `Type in ${selectedLanguage.name}, English, or a mix…`
                    : "Type what you need…"
                }
                rows={2}
                disabled={disabled}
                aria-label="Your message"
              />
              <div className="composer-actions">
                <button
                  className={`mic-button ${recording ? "recording" : ""}`}
                  type="button"
                  onClick={() => void toggleRecording()}
                  disabled={disabled || !voiceInputAvailable}
                  aria-label={recording ? "Stop recording" : "Record a voice message"}
                  title={
                    voiceInputAvailable
                      ? recording
                        ? "Stop recording"
                        : "Record a voice message"
                      : "Speech-to-text is not configured"
                  }
                >
                  <span className="mic-glyph">{recording ? "■" : "●"}</span>
                  <span>{recording ? "Stop" : "Speak"}</span>
                </button>
                <button className="send-button" type="submit" disabled={disabled || !draft.trim()}>
                  <span>{sending ? "Working…" : "Send"}</span>
                  <span aria-hidden="true">↗</span>
                </button>
              </div>
            </form>
            <p className="composer-hint">
              {recording
                ? "Listening… press Stop when you’re done."
                : health?.text_to_speech
                  ? "Voice replies are available when the API has TTS keys."
                  : "Text replies are ready. Voice output is off until SARVAM_API_KEY is added."}
            </p>
          </div>

          <div className="feedback-line" role="status">
            {error && <span className="feedback error">{error}</span>}
            {notice && <span className="feedback notice">{notice}</span>}
            {!error && !notice && loadingCatalog && <span className="feedback">Loading language and state catalog…</span>}
          </div>
        </div>
      </section>

      <section className="debug-panel" aria-label="Last turn details">
        <div className="debug-title">
          <span className="section-kicker">Turn details</span>
          <span className="debug-caption">structured, not guessed</span>
        </div>
        <div className="debug-grid">
          <div>
            <span>intent</span>
            <strong>{lastTurn?.intent ?? "—"}</strong>
          </div>
          <div>
            <span>next question</span>
            <strong>{labelForSlot(lastTurn?.pending_slot)}</strong>
          </div>
          <div className="debug-slots">
            <span>known slots</span>
            <strong>
              {lastTurn && Object.keys(lastTurn.slots ?? {}).length > 0
                ? Object.entries(lastTurn.slots ?? {})
                    .map(([key, value]) => `${labelForSlot(key)}: ${String(value)}`)
                    .join(" · ")
                : "none yet"}
            </strong>
          </div>
          <div>
            <span>matches</span>
            <strong>{lastTurn?.matches?.length ?? 0}</strong>
          </div>
          <div>
            <span>handoff</span>
            <strong className={lastTurn?.needs_escalation ? "warn" : "ok"}>
              {lastTurn?.needs_escalation ? lastTurn.escalation_reason ?? "needed" : "not needed"}
            </strong>
          </div>
        </div>
      </section>

      {lastTurn && (lastTurn.matches?.length ?? 0) > 0 && (
        <section className="matches-panel" aria-label="Eligibility matches">
          <div className="matches-heading">
            <div>
              <span className="section-kicker">Eligibility readout</span>
              <h2>What the agent found</h2>
            </div>
            <span className="plain-note">Reasons come from structured criteria.</span>
          </div>
          <div className="match-list">
            {lastTurn.matches?.map((match) => (
              <article className={`match-card ${match.verdict}`} key={match.benefit_id}>
                <div className="match-card-topline">
                  <span>{match.domain}</span>
                  <span className="verdict">{match.verdict.replaceAll("_", " ")}</span>
                </div>
                <h3>{match.benefit_name}</h3>
                <p>{match.reasons?.[0] ?? "No additional reason was returned."}</p>
                <small>confidence · {Math.round(match.confidence * 100)}%</small>
              </article>
            ))}
          </div>
        </section>
      )}

      <footer className="footer-note">
        <span>Built for a real conversation, not a nationwide coverage claim.</span>
        <span>Kannada · Hindi · English</span>
      </footer>
    </main>
  );
}

export default App;
