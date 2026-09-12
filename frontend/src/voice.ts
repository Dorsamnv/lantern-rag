/** Voice helpers: MediaRecorder STT (via Groq Whisper) + browser TTS. */

export function ttsSupported() {
  return "speechSynthesis" in window;
}

export function micRecordSupported() {
  return Boolean(navigator.mediaDevices?.getUserMedia) && typeof MediaRecorder !== "undefined";
}

export function speechSupported() {
  return micRecordSupported() && ttsSupported();
}

export function speakText(text: string, lang = "en-US"): Promise<void> {
  return new Promise((resolve, reject) => {
    if (!ttsSupported()) {
      reject(new Error("Speech synthesis is not supported in this browser."));
      return;
    }
    window.speechSynthesis.cancel();
    const clean = text
      .replace(/\[\s*S\d+\s*\]/gi, "")
      .replace(/[*_`#]/g, " ")
      .replace(/\s+/g, " ")
      .trim();
    if (!clean) {
      resolve();
      return;
    }

    const utter = new SpeechSynthesisUtterance(clean);
    utter.lang = lang;
    utter.rate = 1;
    utter.pitch = 1;

    const pickVoice = () => {
      const voices = window.speechSynthesis.getVoices();
      const preferred =
        voices.find((v) => v.lang.toLowerCase().startsWith("en") && /natural|neural|google|microsoft/i.test(v.name)) ||
        voices.find((v) => v.lang.toLowerCase().startsWith("en-us")) ||
        voices.find((v) => v.lang.toLowerCase().startsWith("en"));
      if (preferred) utter.voice = preferred;
    };
    pickVoice();
    // Some browsers load voices asynchronously.
    if (window.speechSynthesis.getVoices().length === 0) {
      window.speechSynthesis.onvoiceschanged = () => {
        pickVoice();
      };
    }

    utter.onend = () => resolve();
    utter.onerror = () => reject(new Error("Speech playback failed."));
    window.speechSynthesis.speak(utter);
  });
}

export function stopSpeaking() {
  if (ttsSupported()) {
    window.speechSynthesis.cancel();
  }
}

function pickMimeType(): string {
  const candidates = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg"];
  for (const type of candidates) {
    if (MediaRecorder.isTypeSupported(type)) return type;
  }
  return "";
}

export type MicRecorder = {
  stop: () => Promise<Blob>;
  startedAt: number;
};

export async function startMicRecording(): Promise<MicRecorder> {
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: {
      echoCancellation: true,
      noiseSuppression: true,
      autoGainControl: true,
      channelCount: 1,
    },
  });
  const mimeType = pickMimeType();
  const recorder = mimeType
    ? new MediaRecorder(stream, { mimeType, audioBitsPerSecond: 128000 })
    : new MediaRecorder(stream);
  const chunks: BlobPart[] = [];
  const startedAt = Date.now();

  recorder.ondataavailable = (event) => {
    if (event.data && event.data.size > 0) chunks.push(event.data);
  };

  // timeslice helps some browsers flush audio chunks reliably
  recorder.start(250);

  return {
    startedAt,
    stop: () =>
      new Promise<Blob>((resolve, reject) => {
        const finish = () => {
          stream.getTracks().forEach((t) => t.stop());
          const type = recorder.mimeType || mimeType || "audio/webm";
          resolve(new Blob(chunks, { type }));
        };
        recorder.onerror = () => {
          stream.getTracks().forEach((t) => t.stop());
          reject(new Error("Recording failed."));
        };
        recorder.onstop = finish;
        try {
          if (recorder.state !== "inactive") recorder.stop();
          else finish();
        } catch (err) {
          stream.getTracks().forEach((t) => t.stop());
          reject(err instanceof Error ? err : new Error("Could not stop recording."));
        }
      }),
  };
}
