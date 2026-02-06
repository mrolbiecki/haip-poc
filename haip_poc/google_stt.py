"""Google Cloud Speech-to-Text v2 streaming wrapper."""

from __future__ import annotations

import logging
import os
import subprocess
from collections.abc import Callable, Generator

from google.cloud import speech_v2
from google.protobuf import duration_pb2

from haip_poc.audio import AudioRecorder

logger = logging.getLogger(__name__)


def _get_gcloud_project() -> str:
    """Get the current gcloud project ID."""
    try:
        result = subprocess.run(
            ["gcloud", "config", "get-value", "project"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except Exception as e:
        logger.warning("Failed to get gcloud project: %s", e)
        return ""


class SpeechToText:
    """Stream microphone audio to Google Cloud STT v2 and return transcript."""

    def __init__(
        self,
        language_code: str = "en-US",
        speech_start_timeout_sec: int = 10,
        speech_end_timeout_sec: int = 2,
    ) -> None:
        # Get project ID for v2 API (required)
        self._project_id = os.getenv("GOOGLE_CLOUD_PROJECT") or _get_gcloud_project()
        if not self._project_id:
            raise ValueError(
                "Could not determine Google Cloud project. "
                "Set GOOGLE_CLOUD_PROJECT environment variable or configure gcloud."
            )

        self._client = speech_v2.SpeechClient()
        self._language_code = language_code

        # Build the recognizer resource name
        # Using "_" as recognizer ID means use the default recognizer
        self._recognizer = f"projects/{self._project_id}/locations/global/recognizers/_"

        # Recognition config for v2 API with explicit audio encoding
        self._recognition_config = speech_v2.RecognitionConfig(
            explicit_decoding_config=speech_v2.ExplicitDecodingConfig(
                encoding=speech_v2.ExplicitDecodingConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=16000,
                audio_channel_count=1,
            ),
            language_codes=[language_code],
            model="long",  # Use 'long' model for better accuracy on longer utterances
            features=speech_v2.RecognitionFeatures(
                enable_automatic_punctuation=True,
            ),
        )

        # Streaming features with voice activity detection
        self._streaming_features = speech_v2.StreamingRecognitionFeatures(
            interim_results=True,
            enable_voice_activity_events=True,
            voice_activity_timeout=speech_v2.StreamingRecognitionFeatures.VoiceActivityTimeout(
                speech_start_timeout=duration_pb2.Duration(seconds=speech_start_timeout_sec),
                speech_end_timeout=duration_pb2.Duration(seconds=speech_end_timeout_sec),
            ),
        )

        # Build streaming config
        self._streaming_config = speech_v2.StreamingRecognitionConfig(
            config=self._recognition_config,
            streaming_features=self._streaming_features,
        )

    def transcribe_stream(
        self,
        recorder: AudioRecorder,
        max_seconds: int = 30,
        on_interim: Callable[[str], None] | None = None,
    ) -> str:
        """Record from *recorder* and return the final transcript.

        Recording must already be started on *recorder*.  This method reads
        chunks until speech ends (detected via SPEECH_ACTIVITY_END event) or
        *max_seconds* elapses as a fallback timeout.

        Args:
            recorder: The audio recorder to read from.
            max_seconds: Maximum recording duration (fallback timeout).
            on_interim: Optional callback for real-time interim transcriptions.
        """
        from google.api_core import exceptions as gapi_exceptions

        requests = self._request_generator(recorder, max_seconds)
        responses = self._client.streaming_recognize(requests=requests)

        transcript_parts: list[str] = []
        speech_started = False

        # Alias for cleaner event type comparisons
        event_types = speech_v2.StreamingRecognizeResponse.SpeechEventType

        try:
            for response in responses:
                event_type = response.speech_event_type

                # Handle voice activity events
                if event_type == event_types.SPEECH_ACTIVITY_BEGIN:
                    logger.info("Speech activity started")
                    speech_started = True
                elif event_type == event_types.SPEECH_ACTIVITY_END:
                    logger.info("Speech activity ended (user stopped speaking)")
                    if speech_started:
                        # Speech ended - signal to stop after we get final results
                        recorder.signal_stop()

                for result in response.results:
                    if result.is_final:
                        text = result.alternatives[0].transcript
                        logger.info("STT final: %s", text)
                        transcript_parts.append(text)
                        speech_started = True
                    elif on_interim and result.alternatives:
                        # Send interim results to callback
                        interim_text = result.alternatives[0].transcript
                        on_interim(interim_text)

        except gapi_exceptions.Cancelled:
            # Stream cancelled when we stop recording - this is expected
            logger.debug("Stream cancelled (expected on timeout/stop)")
        except gapi_exceptions.OutOfRange as e:
            # Stream exceeded time limit - expected for long streams
            logger.debug("Stream ended (time limit): %s", e)

        return " ".join(transcript_parts).strip()

    # -- internal ------------------------------------------------------------

    def _request_generator(
        self,
        recorder: AudioRecorder,
        max_seconds: int,
    ) -> Generator[speech_v2.StreamingRecognizeRequest]:
        """Yield streaming requests from the recorder's audio queue."""
        import time

        # First request must contain the config
        yield speech_v2.StreamingRecognizeRequest(
            recognizer=self._recognizer,
            streaming_config=self._streaming_config,
        )

        deadline = time.monotonic() + max_seconds
        chunk_count = 0
        while time.monotonic() < deadline and recorder.is_recording:
            chunk = recorder.get_chunk(timeout=0.5)
            if chunk:
                chunk_count += 1
                if chunk_count <= 3 or chunk_count % 10 == 0:
                    logger.debug("Sending audio chunk %d (%d bytes)", chunk_count, len(chunk))
                yield speech_v2.StreamingRecognizeRequest(audio=chunk)

        logger.debug("Audio generator finished after %d chunks", chunk_count)
