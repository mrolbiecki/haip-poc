"""Interview agent – state machine that drives the conversation."""

from __future__ import annotations

import enum
import json
import logging
import os
import subprocess
import threading
from datetime import UTC, datetime
from pathlib import Path

from google import genai
from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from haip_poc.audio import AudioPlayer, AudioRecorder
from haip_poc.google_stt import SpeechToText
from haip_poc.google_tts import TextToSpeech
from haip_poc.models import FollowUp, Question, Scenario

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


class AgentState(enum.Enum):
    IDLE = "idle"
    WAITING = "waiting"  # timer counting down
    ASKING = "asking"
    LISTENING = "listening"
    PROCESSING = "processing"
    DONE = "done"


class InterviewAgent(QObject):
    """Drives a single interview session based on a :class:`Scenario`.

    Emits Qt signals so the overlay can react to state changes.
    """

    # Signals ----------------------------------------------------------------
    state_changed = pyqtSignal(str)  # new AgentState value
    question_text = pyqtSignal(str)  # current question being asked
    status_text = pyqtSignal(str)  # short status label
    interview_done = pyqtSignal()

    def __init__(self, scenario: Scenario, output_dir: Path, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._scenario = scenario
        self._output_dir = output_dir
        self._output_dir.mkdir(parents=True, exist_ok=True)

        # Google Cloud components
        self._tts = TextToSpeech(scenario.voice)
        self._stt = SpeechToText(scenario.voice.language_code)
        self._player = AudioPlayer()
        self._recorder = AudioRecorder()

        # Gemini client for follow-up selection (using Vertex AI)
        project_id = os.getenv("GOOGLE_CLOUD_PROJECT") or _get_gcloud_project()
        location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
        
        if not project_id:
            raise ValueError(
                "Could not determine Google Cloud project. "
                "Set GOOGLE_CLOUD_PROJECT environment variable or configure gcloud."
            )
        
        logger.info("Initializing Gemini with Vertex AI (project=%s, location=%s)", project_id, location)
        self._gemini = genai.Client(vertexai=True, project=project_id, location=location)

        # Interview state
        self._state = AgentState.IDLE
        self._question_idx = 0
        self._transcript: list[dict] = []

        # Trigger timer (configured but not started yet)
        self._trigger_timer = QTimer(self)
        self._trigger_timer.setSingleShot(True)
        self._trigger_timer.timeout.connect(self._on_trigger)

    # -- public API ----------------------------------------------------------

    def start(self) -> None:
        """Arm the trigger and begin waiting."""
        trigger = self._scenario.trigger
        delay_ms = trigger.delay_seconds * 1000
        logger.info("Agent armed – will trigger in %d s", trigger.delay_seconds)
        self._set_state(AgentState.WAITING)
        self.status_text.emit(f"Interview in {trigger.delay_seconds}s…")
        self._trigger_timer.start(delay_ms)

    # -- state management ----------------------------------------------------

    def _set_state(self, state: AgentState) -> None:
        self._state = state
        self.state_changed.emit(state.value)
        logger.info("Agent state → %s", state.value)

    # -- trigger callback ----------------------------------------------------

    def _on_trigger(self) -> None:
        """Called when the scenario trigger fires (runs on the main Qt thread).

        We spawn a worker thread for the blocking interview loop so the
        Qt event loop stays responsive.
        """
        logger.info("Trigger fired – starting interview")
        self._question_idx = 0
        thread = threading.Thread(target=self._run_interview, daemon=True)
        thread.start()

    def _run_interview(self) -> None:
        """Blocking interview loop – runs in a worker thread."""
        self._ask_current_question()

    # -- interview loop ------------------------------------------------------

    def _ask_current_question(self) -> None:
        if self._question_idx >= len(self._scenario.questions):
            self._finish()
            return

        question = self._scenario.questions[self._question_idx]
        self._ask(question)

    def _ask(self, question: Question | FollowUp) -> None:
        """Speak *question*, listen for response, then decide next step."""
        self._set_state(AgentState.ASKING)
        self.question_text.emit(question.text)
        self.status_text.emit("Speaking…")

        # Synthesize and play the question
        audio = self._tts.synthesize(question.text)
        self._player.play_bytes(audio)

        # Listen
        self._set_state(AgentState.LISTENING)
        self.status_text.emit("Listening…")

        listen_secs = question.listen_seconds if isinstance(question, Question) else 30
        self._recorder.start()
        transcript = self._stt.transcribe_stream(self._recorder, max_seconds=listen_secs)
        raw_audio = self._recorder.stop()

        # Save audio
        q_id = question.id
        wav_path = self._output_dir / f"{q_id}.wav"
        if raw_audio:
            self._recorder.save_wav(raw_audio, wav_path)

        # Log to transcript
        entry = {
            "question_id": q_id,
            "question_text": question.text,
            "response_transcript": transcript,
            "audio_file": str(wav_path),
            "timestamp": datetime.now(tz=UTC).isoformat(),
        }
        self._transcript.append(entry)
        logger.info("Response for %s: %s", q_id, transcript[:120])

        # Decide follow-up (only for top-level questions with follow-ups)
        self._set_state(AgentState.PROCESSING)
        self.status_text.emit("Thinking…")

        if isinstance(question, Question) and question.follow_ups and transcript.strip():
            follow_up = self._select_follow_up(question, transcript)
            if follow_up:
                self._ask(follow_up)
                return

        # Move to next question
        self._question_idx += 1
        self._ask_current_question()

    def _finish(self) -> None:
        self._set_state(AgentState.DONE)
        self.status_text.emit("Interview complete")
        self.question_text.emit("")
        self._save_transcript()
        self.interview_done.emit()

    # -- Gemini follow-up selection ------------------------------------------

    def _select_follow_up(self, question: Question, response: str) -> FollowUp | None:
        """Use Gemini to pick the best follow-up (or none)."""
        follow_ups_text = "\n".join(
            f"  {i}. [{fu.id}] {fu.text}" for i, fu in enumerate(question.follow_ups, 1)
        )
        prompt = (
            "You are helping conduct a game-testing interview. The tester was asked:\n"
            f'  "{question.text}"\n\n'
            f"They responded:\n"
            f'  "{response}"\n\n'
            f"Available follow-up questions:\n{follow_ups_text}\n\n"
            "Based on the response, should we ask a follow-up? If yes, reply with ONLY the "
            "follow-up id (e.g. q1_f1). If no follow-up is needed, reply with NONE."
        )
        try:
            gemini_response = self._gemini.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
            )
            choice = gemini_response.text.strip()
            logger.info("Gemini follow-up choice: %s", choice)

            if choice.upper() == "NONE":
                return None

            for fu in question.follow_ups:
                if fu.id == choice:
                    return fu

            logger.warning("Gemini returned unknown follow-up id: %s", choice)
        except Exception:
            logger.exception("Gemini follow-up selection failed")

        return None

    # -- transcript persistence ----------------------------------------------

    def _save_transcript(self) -> None:
        path = self._output_dir / "transcript.json"
        data = {
            "scenario": self._scenario.name,
            "completed_at": datetime.now(tz=UTC).isoformat(),
            "entries": self._transcript,
        }
        path.write_text(json.dumps(data, indent=2))
        logger.info("Transcript saved → %s", path)
