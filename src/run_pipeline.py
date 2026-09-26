"""Run acquisition, preparation, and validation in order."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


SRC = Path(__file__).resolve().parent


def run(script: str, *args: str) -> None:
    subprocess.run([sys.executable, str(SRC / script), *args], check=True)


if __name__ == "__main__":
    run("download_data.py", "--overwrite")
    run("prepare_data.py")
    run("validate_data.py")
