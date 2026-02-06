"""Google Cloud Speech-to-Text streaming wrapper."""

from __future__ import annotations

import logging
from collections.abc import Generator

from google.cloud import speech

from haip_poc.audio import SAMPLE_RATE, AudioRecorder

logger = logging.getLogger(__name__)


class SpeechToText:
    """Stream microphone audio to Google Cloud STT and return transcript."""

    def __init__(self, language_code: str = "en-US") -> None:
        self._client = speech.SpeechClient()
        self._config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=SAMPLE_RATE,
            language_code=language_code,
            enable_automatic_punctuation=True,
        )
        self._streaming_config = speech.StreamingRecognitionConfig(
            config=self._config,
            interim_results=False,
        )

    def transcribe_stream(
        self,
        recorder: AudioRecorder,
        max_seconds: int = 30,
    ) -> str:
        """Record from *recorder* and return the final transcript.

        Recording must already be started on *recorder*.  This method reads
        chunks until *max_seconds* elapses, then returns the concatenated
        final transcript.
        """
        requests = self._audio_generator(recorder, max_seconds)
        responses = self._client.streaming_recognize(self._streaming_config, requests)

        transcript_parts: list[str] = []
        for response in responses:
            for result in response.results:
                if result.is_final:
                    text = result.alternatives[0].transcript
                    logger.info("STT final: %s", text)
                    transcript_parts.append(text)

        return " ".join(transcript_parts).strip()

    # -- internal ------------------------------------------------------------

    @staticmethod
    def _audio_generator(
        recorder: AudioRecorder,
        max_seconds: int,
    ) -> Generator[speech.StreamingRecognizeRequest]:
        """Yield streaming requests from the recorder's audio queue."""
        import time

        deadline = time.monotonic() + max_seconds
        while time.monotonic() < deadline and recorder.is_recording:
            chunk = recorder.get_chunk(timeout=0.5)
            if chunk:
                yield speech.StreamingRecognizeRequest(audio_content=chunk)
