"""Shared control behavior through real execution and transport boundaries."""
import json
import os
from pathlib import Path
import subprocess
import sys


def test_control_identity_rejects_foreign_and_retired_workers(tmp_path, monkeypatch):
    import asyncio
    import runpy
    fixture = runpy.run_path(str(Path(__file__).parent / 'fixtures' / 'control_boundaries.py'))
    asyncio.run(fixture['exercise_control_boundaries'](tmp_path, monkeypatch))
