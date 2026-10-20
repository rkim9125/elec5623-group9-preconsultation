import React, { useEffect, useRef, useState } from "react";
import Icon from "./Icons.jsx";
import { request } from "./api.js";
import { useLocale } from "./i18n.jsx";

// Audio lives only in memory. A transcript is always editable before submission.
export default function VoiceComposer({
  value = "",
  onChange,
  onSend,
  onTranscript,
  disabled = false,
  voiceEnabled = true,
  onError,
  placeholder,
  maxLength = 6000,
  inputRef,
  id,
  onActivity,
}) {
  const { locale, t } = useLocale();
  const [phase, setPhase] = useState("idle");
  const [seconds, setSeconds] = useState(0);
  const [levels, setLevels] = useState(Array(44).fill(3));
  const recording = useRef(null);
  const mounted = useRef(true);
  const operation = useRef(0);
  const phaseRef = useRef(phase);
  phaseRef.current = phase;
  const activityCallback = useRef(onActivity);
  activityCallback.current = onActivity;
  useEffect(() => {
    activityCallback.current?.(phase !== "idle");
  }, [phase]);
  function release(item) {
    if (!item) return;
    item.stream?.getTracks().forEach((track) => track.stop());
    if (item.frame) cancelAnimationFrame(item.frame);
    item.context?.close().catch(() => {});
    clearTimeout(item.limit);
  }
  function cancel() {
    operation.current += 1;
    const item = recording.current;
    if (item) {
      item.cancelled = true;
      item.abort?.abort();
      if (item.media?.state === "recording") item.media.stop();
      release(item);
    }
    recording.current = null;
    if (mounted.current) setPhase("idle");
  }
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      cancel();
      activityCallback.current?.(false);
    };
  }, []);
  useEffect(() => {
    if (phase !== "recording") return;
    const timer = setInterval(() => setSeconds((n) => n + 1), 1000);
    return () => clearInterval(timer);
  }, [phase]);
  useEffect(() => {
    if (disabled && phaseRef.current !== "idle") cancel();
  }, [disabled]);
  async function transcribe(item) {
    if (!item || item.cancelled || item.transcribing) return;
    item.transcribing = true;
    onError?.("");
    setPhase("transcribing");
    const generation = operation.current;
    const body = new FormData();
    body.append(
      "file",
      item.blob,
      `voice-note.${item.blob.type.includes("mp4") ? "m4a" : "webm"}`,
    );
    body.append("locale", locale);
    item.abort = new AbortController();
    try {
      const result = await request("/transcriptions", {
        method: "POST",
        body,
        signal: item.abort.signal,
      });
      if (
        !mounted.current ||
        item.cancelled ||
        generation !== operation.current
      )
        return;
      const transcript = result.text?.trim();
      if (!transcript)
        throw new Error(t("No speech was detected. Please try again."));
      if (onTranscript) onTranscript(transcript);
      else {
        const next = [value, transcript].filter(Boolean).join("\n");
        if (next.length > maxLength)
          throw new Error(
            t("This answer is too long. Shorten it and try again."),
          );
        onChange?.(next);
      }
      setPhase("idle");
      recording.current = null;
    } catch (err) {
      if (
        mounted.current &&
        !item.cancelled &&
        generation === operation.current
      ) {
        onError?.(err.message);
        setPhase("stopped");
      }
    } finally {
      item.transcribing = false;
    }
  }
  async function start() {
    onError?.("");
    if (phaseRef.current !== "idle" || !voiceEnabled) return;
    setPhase("requesting");
    const generation = ++operation.current;
    let item;
    try {
      if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder)
        throw new Error(
          t("Voice input needs a supported browser on HTTPS or localhost."),
        );
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      if (!mounted.current || generation !== operation.current) {
        stream.getTracks().forEach((track) => track.stop());
        return;
      }
      item = { stream, chunks: [], cancelled: false };
      recording.current = item;
      const mimeType = [
        "audio/webm;codecs=opus",
        "audio/mp4",
        "audio/webm",
      ].find((type) => MediaRecorder.isTypeSupported(type));
      const media = new MediaRecorder(
        stream,
        mimeType ? { mimeType } : undefined,
      );
      item.media = media;
      recording.current = item;
      media.ondataavailable = (event) => {
        if (event.data.size) item.chunks.push(event.data);
      };
      media.onstop = () => {
        release(item);
        if (!mounted.current || item.cancelled) return;
        item.blob = new Blob(item.chunks, {
          type: media.mimeType || "audio/webm",
        });
        transcribe(item);
      };
      media.onerror = () => {
        if (!item.cancelled) {
          cancel();
          onError?.(t("Recording failed. Please try again."));
        }
      };
      // Waveform reflects actual microphone amplitude, rather than decorative random data.
      const Context = window.AudioContext || window.webkitAudioContext;
      if (Context) {
        try {
          item.context = new Context();
          const analyser = item.context.createAnalyser();
          analyser.fftSize = 256;
          item.context.createMediaStreamSource(stream).connect(analyser);
          const data = new Uint8Array(analyser.frequencyBinCount);
          let last = 0;
          const draw = (time) => {
            if (item.cancelled) return;
            if (time - last > 75) {
              analyser.getByteTimeDomainData(data);
              const peak = Math.max(...data.map((v) => Math.abs(v - 128)));
              setLevels((old) => [
                ...old.slice(1),
                Math.max(3, Math.min(46, peak * 1.5)),
              ]);
              last = time;
            }
            item.frame = requestAnimationFrame(draw);
          };
          item.frame = requestAnimationFrame(draw);
        } catch {
          /* Audio capture remains available without waveform analysis. */
        }
      }
      media.start(250);
      item.limit = setTimeout(stopRecording, 120000);
      setLevels(Array(44).fill(3));
      setSeconds(0);
      setPhase("recording");
    } catch (err) {
      release(item);
      if (mounted.current && generation === operation.current) {
        setPhase("idle");
        onError?.(
          err.name === "NotAllowedError"
            ? t(
                "Microphone access was denied. Allow access in your browser or type your answer.",
              )
            : err.message,
        );
      }
    }
  }
  function stopRecording() {
    const item = recording.current;
    if (item?.media.state === "recording") {
      setPhase("transcribing");
      item.media.stop();
    }
  }
  const active = phase !== "idle";
  return (
    <div className="voice-composer-wrap">
      <div
        className={`voice-composer ${active ? "voice-active" : ""}`}
        data-phase={phase}
      >
        {active ? (
          <>
            <button
              type="button"
              className="voice-circle quiet"
              onClick={cancel}
              aria-label={t("Cancel recording")}
            >
              <Icon name="close" size={22} />
            </button>
            <div className="voice-wave" aria-hidden="true">
              {levels.map((height, i) => (
                <span key={i} style={{ height }} />
              ))}
            </div>
            <span className="voice-time">
              {String(Math.floor(seconds / 60)).padStart(2, "0")}:
              {String(seconds % 60).padStart(2, "0")}
            </span>
            {phase === "recording" && (
              <button
                type="button"
                className="voice-circle dark"
                onClick={stopRecording}
                aria-label={t("Stop recording")}
              >
                <Icon name="stop" size={20} />
              </button>
            )}
            {phase === "stopped" && (
              <button
                type="button"
                className="voice-circle dark"
                onClick={() => transcribe(recording.current)}
                aria-label={t("Retry transcription")}
              >
                <Icon name="retry" size={23} />
              </button>
            )}
            {["requesting", "transcribing"].includes(phase) && (
              <span className="voice-circle dark" aria-hidden="true">
                <span className="spinner" />
              </span>
            )}
          </>
        ) : (
          <>
            <textarea
              id={id}
              ref={inputRef}
              aria-label={t("Your response")}
              rows={1}
              value={value}
              maxLength={maxLength}
              onChange={(event) => onChange?.(event.target.value)}
              placeholder={
                placeholder || t("Type or tell us in your own words…")
              }
              disabled={disabled}
              onKeyDown={(event) => {
                if (
                  onSend &&
                  (event.metaKey || event.ctrlKey) &&
                  event.key === "Enter"
                ) {
                  event.preventDefault();
                  if (value.trim() && !disabled) onSend();
                }
              }}
            />
            <button
              type="button"
              className="voice-mic"
              disabled={disabled || !voiceEnabled}
              onClick={start}
              aria-label={t("Record a voice response")}
              title={t("Use my voice")}
            >
              <Icon name="mic" size={24} />
            </button>
            {onSend && value.trim() ? (
              <button
                type="button"
                className="voice-circle dark"
                disabled={disabled}
                onClick={onSend}
                aria-label={t("Send response")}
              >
                <span className="send-up">
                  <Icon name="arrow" size={24} />
                </span>
              </button>
            ) : (
              <button
                type="button"
                className="voice-circle dark"
                disabled={disabled || !voiceEnabled}
                onClick={start}
                aria-label={t("Start voice input")}
              >
                <span className="voice-symbol" aria-hidden="true">
                  {[12, 24, 31, 19, 10].map((height, i) => (
                    <i key={i} style={{ height }} />
                  ))}
                </span>
              </button>
            )}
          </>
        )}
      </div>
      <p className="voice-caption" role="status">
        {t(
          phase === "recording"
            ? "Listening… take your time. Up to 2 minutes."
            : phase === "stopped"
              ? "Transcription failed. Retry or discard this recording."
              : phase === "transcribing"
                ? "Turning your voice into text…"
                : phase === "requesting"
                  ? "Waiting for microphone permission…"
                  : !voiceEnabled
                    ? "Agree to AI processing to enable voice input."
                    : "Speak naturally. You can edit the transcript before sending.",
        )}
      </p>
    </div>
  );
}
