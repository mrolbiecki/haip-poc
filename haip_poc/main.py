"""Entry point – wires overlay, agent, and audio together."""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

from PyQt6.QtWidgets import QApplication

from haip_poc.agent import AgentState, InterviewAgent
from haip_poc.models import Scenario

logger = logging.getLogger(__name__)

OUTPUT_ROOT = Path("output")


def _load_scenario(path: str) -> Scenario:
    text = Path(path).read_text()
    return Scenario.model_validate_json(text)


def main() -> None:
    parser = argparse.ArgumentParser(description="HAIP – Game-tester interview agent")
    parser.add_argument(
        "--scenario",
        required=True,
        help="Path to a scenario JSON file",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    scenario = _load_scenario(args.scenario)
    logger.info("Loaded scenario: %s (%d questions)", scenario.name, len(scenario.questions))

    # Session output directory
    session_id = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S")
    output_dir = OUTPUT_ROOT / f"{scenario.name}_{session_id}"

    # Qt application
    app = QApplication(sys.argv)

    # Overlay
    # Overlay
    from haip_poc.overlay import AgentWindow

    window = AgentWindow()
    window.show()

    # Agent
    agent = InterviewAgent(scenario, output_dir)

    # Connect agent signals → window
    def on_state_changed(state_str: str) -> None:
        state = AgentState(state_str)
        if state == AgentState.WAITING:
            window.icon.set_active(False)
        elif state == AgentState.ASKING:
            window.icon.set_active(True)
        elif state == AgentState.LISTENING:
            window.icon.set_listening(True)
        elif state == AgentState.PROCESSING:
            window.icon.set_active(True)
        elif state == AgentState.DONE:
            window.icon.set_active(False)

    agent.state_changed.connect(on_state_changed)
    agent.question_text.connect(window.set_question)
    agent.status_text.connect(window.set_status)

    # Arm the trigger (non-blocking – just starts a QTimer).
    # The agent internally spawns a worker thread when the timer fires.
    agent.start()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
