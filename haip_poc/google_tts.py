"""Google Cloud Text-to-Speech wrapper."""

from __future__ import annotations

import logging

from google.cloud import texttospeech

from haip_poc.models import VoiceConfig

logger = logging.getLogger(__name__)


class TextToSpeech:
    """Synthesise speech from text using Google Cloud TTS."""

    def __init__(self, voice_config: VoiceConfig | None = None) -> None:
        self._client = texttospeech.TextToSpeechClient()
        vc = voice_config or VoiceConfig()
        self._voice = texttospeech.VoiceSelectionParams(
            language_code=vc.language_code,
            name=vc.name,
        )
        self._audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.LINEAR16,
            sample_rate_hertz=24_000,
        )

    def synthesize(self, text: str) -> bytes:
        """Return raw LINEAR16 audio bytes for *text*."""
        logger.info("TTS synthesizing: %s", text[:80])
        response = self._client.synthesize_speech(
            input=texttospeech.SynthesisInput(text=text),
            voice=self._voice,
            audio_config=self._audio_config,
        )
        return response.audio_content
