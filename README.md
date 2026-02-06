# HAIP – Game-Tester Interview Agent (POC)

A transparent desktop overlay that interviews game testers via voice during gameplay.  
After a configurable trigger (e.g. time delay), an AI agent asks predefined questions using Google Cloud TTS, captures spoken responses via STT, and optionally selects follow-up questions using Gemini.

## Quick start

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager
- A Google Cloud project with these APIs enabled:
  - Cloud Text-to-Speech
  - Cloud Speech-to-Text
  - Generative Language (Gemini)
- Authenticated via `gcloud auth application-default login` **or** a service-account key

### Install & run

```bash
# Install dependencies
uv sync

# Set GCP credentials (if using a service-account key)
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json

# Run with the example scenario (triggers after 10 s)
uv run haip --scenario scenarios/example_scenario.json
```

## Project structure

```
haip_poc/
  main.py          – entry point, wires everything together
  models.py        – Pydantic models for scenario JSON
  agent.py         – interview state machine + Gemini follow-up selection
  audio.py         – mic capture, playback, WAV recording
  google_tts.py    – Google Cloud Text-to-Speech wrapper
  google_stt.py    – Google Cloud Speech-to-Text streaming wrapper
  overlay.py       – PyQt6 transparent always-on-top overlay
scenarios/
  example_scenario.json
```

## Scenario format

Scenarios are defined as JSON files. See `scenarios/example_scenario.json` for a full example.

```jsonc
{
  "name": "session_name",
  "voice": { "language_code": "en-US", "name": "en-US-Neural2-D" },
  "trigger": { "type": "time", "delay_seconds": 300 },
  "questions": [
    {
      "id": "q1",
      "text": "How are you finding the game so far?",
      "listen_seconds": 30,
      "follow_ups": [
        { "id": "q1_f1", "text": "Could you elaborate?" }
      ]
    }
  ]
}
```

The `trigger.type` field is a discriminator — only `"time"` is supported today, but the system is designed for easy extension.

## Development

```bash
# Format code
uv run ruff format haip_poc/

# Lint
uv run ruff check haip_poc/

# Lint + auto-fix
uv run ruff check --fix haip_poc/
```
