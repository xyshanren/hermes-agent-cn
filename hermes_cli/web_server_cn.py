"""CN-only dashboard API routes.

Upstream split ``hermes_cli/web_server.py`` into an app-assembly module plus
sibling routers (``hermes_cli/web_server_*.py``). CN keeps its own routes in
this module so a base bump never collides with them: the upstream file stays
untouched apart from one ``include_router`` line.

Routes here:

* ``GET /api/audio/elevenlabs/voices`` — voice list for the TTS voice picker.
  The key stays server-side; only non-secret voice metadata is returned.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any, Dict, Optional

from fastapi import APIRouter

router = APIRouter()

# Fixed upstream endpoint: the voice list of the configured TTS provider.
_ELEVENLABS_VOICES_URL = "https://api.elevenlabs.io/v1/voices"


@router.get("/api/audio/elevenlabs/voices")
async def get_elevenlabs_voices(profile: Optional[str] = None):
    """Return ElevenLabs voices when an API key is configured.

    Only non-secret voice metadata is returned; the key stays server-side.
    """
    from hermes_cli.config import load_env
    from hermes_cli.web_server_profiles import _config_profile_scope
    from tools.url_safety import create_ssrf_safe_client, is_safe_url

    # Config-only scope (await-safe): the key lookup reads the requested
    # profile's .env, matching the profile the settings UI writes to.
    with _config_profile_scope(profile):
        api_key = (load_env().get("ELEVENLABS_API_KEY") or "").strip()
    if not api_key:
        # Fallback for env-only deployments — scope-aware (Slack pattern):
        # under multiplex os.environ may hold another profile's key, so
        # honor the installed scope's verdict before touching the env.
        try:
            from agent.secret_scope import UnscopedSecretError, get_secret

            try:
                api_key = (get_secret("ELEVENLABS_API_KEY") or "").strip()
            except UnscopedSecretError:
                api_key = (os.environ.get("ELEVENLABS_API_KEY") or "").strip()
        except Exception:
            api_key = (os.environ.get("ELEVENLABS_API_KEY") or "").strip()
    if not api_key:
        return {"available": False, "voices": []}
    if not is_safe_url(_ELEVENLABS_VOICES_URL):
        return {"available": False, "voices": []}

    def _fetch() -> Dict[str, Any]:
        # SSRF-safe client: connect-time validation, no redirect following.
        with create_ssrf_safe_client(timeout=10.0, follow_redirects=False) as client:
            resp = client.get(
                _ELEVENLABS_VOICES_URL,
                headers={"Accept": "application/json", "xi-api-key": api_key},
            )
            resp.raise_for_status()
            return resp.json()

    try:
        payload = await asyncio.get_running_loop().run_in_executor(None, _fetch)
    except Exception:
        return {"available": False, "voices": []}

    voices = []
    for voice in (payload or {}).get("voices") or []:
        if not isinstance(voice, dict):
            continue
        voices.append({
            "voice_id": voice.get("voice_id"),
            "name": voice.get("name"),
            "category": voice.get("category"),
            "preview_url": voice.get("preview_url"),
        })
    return {"available": True, "voices": voices}
