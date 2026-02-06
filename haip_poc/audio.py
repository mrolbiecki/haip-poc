"""Audio capture, playback, and WAV recording utilities."""

from __future__ import annotations

import io
import logging
import queue
import threading
from pathlib import Path

import numpy as np
import sounddevice as sd
import soundfile as sf

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16_000  # 16 kHz – good balance for speech
CHANNELS = 1
DTYPE = "int16"
BLOCK_SIZE = 1600  # 100 ms chunks at 16 kHz


class AudioPlayer:
    """Play raw PCM / WAV audio through the default output device."""

    def play_bytes(self, audio_bytes: bytes, sample_rate: int = 24_000) -> None:
        """Play LINEAR16 audio bytes synchronously."""
        data = np.frombuffer(audio_bytes, dtype=np.int16)
        sd.play(data, samplerate=sample_rate, blocking=True)

    def play_wav(self, path: Path) -> None:
        data, sr = sf.read(path, dtype="int16")
        sd.play(data, samplerate=sr, blocking=True)


class AudioRecorder:
    """Record audio from the microphone.

    Usage::

        recorder = AudioRecorder()
        recorder.start()
        # ... wait ...
        audio_data = recorder.stop()
        recorder.save_wav(audio_data, Path("out.wav"))

    While recording, raw audio chunks are also available via ``get_chunk()``
    for streaming to STT.
    """

    def __init__(self, sample_rate: int = SAMPLE_RATE, channels: int = CHANNELS) -> None:
        self.sample_rate = sample_rate
        self.channels = channels
        self._queue: queue.Queue[bytes] = queue.Queue()
        self._frames: list[bytes] = []
        self._stream: sd.RawInputStream | None = None
        self._recording = False
        self._lock = threading.Lock()

    # -- public API ----------------------------------------------------------

    def start(self) -> None:
        """Start capturing audio from the default input device."""
        with self._lock:
            if self._recording:
                return
            self._frames.clear()
            while not self._queue.empty():
                self._queue.get_nowait()
            self._stream = sd.RawInputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype=DTYPE,
                blocksize=BLOCK_SIZE,
                callback=self._callback,
            )
            self._stream.start()
            self._recording = True
            logger.info("Audio recording started (rate=%d)", self.sample_rate)

    def stop(self) -> bytes:
        """Stop recording and return the full captured audio as raw bytes."""
        with self._lock:
            if not self._recording:
                return b""
            assert self._stream is not None
            self._stream.stop()
            self._stream.close()
            self._stream = None
            self._recording = False
        raw = b"".join(self._frames)
        logger.info("Audio recording stopped – captured %d bytes", len(raw))
        return raw

    @property
    def is_recording(self) -> bool:
        return self._recording

    def get_chunk(self, timeout: float = 0.5) -> bytes | None:
        """Get the next audio chunk (for streaming to STT). Returns *None* on timeout."""
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None

    # -- persistence ---------------------------------------------------------

    def save_wav(self, raw_audio: bytes, path: Path) -> Path:
        """Save raw LINEAR16 audio bytes as a WAV file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        data = np.frombuffer(raw_audio, dtype=np.int16)
        sf.write(str(path), data, self.sample_rate)
        logger.info("Saved WAV → %s", path)
        return path

    # -- internal ------------------------------------------------------------

    def _callback(self, indata: bytes, frames: int, time_info: object, status: object) -> None:
        if status:
            logger.warning("sounddevice status: %s", status)
        chunk = bytes(indata)
        self._frames.append(chunk)
        self._queue.put(chunk)


def raw_to_wav_bytes(raw: bytes, sample_rate: int = SAMPLE_RATE) -> bytes:
    """Convert raw LINEAR16 bytes to in-memory WAV bytes."""
    buf = io.BytesIO()
    data = np.frombuffer(raw, dtype=np.int16)
    sf.write(buf, data, sample_rate, format="WAV")
    buf.seek(0)
    return buf.read()
