"""A config saved while a profile connects must remain pending for the next scan."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from gateway.config import GatewayConfig, Platform
from gateway.run import GatewayRunner


