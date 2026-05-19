"""Project root resolution for scripts run from any working directory."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
