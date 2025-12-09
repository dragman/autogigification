"""AWS Lambda entry point for creating Spotify playlists."""

import base64
import json
import logging
import os
from typing import Any, Dict, Tuple

from dotenv import load_dotenv

from ag.run import playlist_result_to_payload, run_playlist_job

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Load environment variables (client IDs, secrets, etc.) when running outside AWS config.
load_dotenv()

ENABLE_CORS = os.environ.get("ENABLE_CORS", "").lower() in {"1", "true", "yes"}
_DEBUGPY_INITIALIZED = False


def _maybe_enable_debugpy() -> bool:
    global _DEBUGPY_INITIALIZED
    if _DEBUGPY_INITIALIZED:
        return _DEBUGPY_INITIALIZED

    if os.environ.get("ENABLE_DEBUGPY", "").lower() not in {"1", "true", "yes"}:
        return _DEBUGPY_INITIALIZED

    try:
        import debugpy

        host = os.environ.get("DEBUGPY_HOST", "0.0.0.0")
        port = int(os.environ.get("DEBUGPY_PORT", "5678"))
        debugpy.listen((host, port))
        logger.info("debugpy listening on %s:%s", host, port)
        _DEBUGPY_INITIALIZED = True
    except Exception:
        logger.exception("Failed to enable debugpy")

    return _DEBUGPY_INITIALIZED


_maybe_enable_debugpy()


# Comma-separated list of allowed tokens
# e.g. APP_TOKENS="dmoney_token_...,bro_token_..."
APP_TOKENS = os.environ.get("APP_TOKENS", "")

VALID_TOKENS = {t.strip() for t in APP_TOKENS.split(",") if t.strip()}


def _response(status: int, body: Dict[str, Any]) -> Dict[str, Any]:
    headers = {"Content-Type": "application/json"}
    if ENABLE_CORS:
        headers.update(
            {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type,Authorization",
                "Access-Control-Allow-Methods": "OPTIONS,POST",
            }
        )

    return {
        "statusCode": status,
        "headers": headers,
        "body": json.dumps(body),
    }


def _unauthorized(message="unauthorized"):
    return _response(401, {"error": message})


def _bad_request(message="bad_request"):
    return _response(400, {"error": message})


def _http_method(event: Dict[str, Any]) -> str:
    context = event.get("requestContext") or {}
    http_info = context.get("http") or {}
    method = http_info.get("method") or event.get("httpMethod") or ""
    return method.upper()


def _parse_body(event: Dict[str, Any]) -> Dict[str, Any]:
    raw_body = event.get("body") or "{}"
    if event.get("isBase64Encoded"):
        raw_body = base64.b64decode(raw_body).decode("utf-8")
    return json.loads(raw_body)


def main_logic(payload: Dict[str, Any]) -> Dict[str, Any]:
    band_names = payload.get("band_names")
    playlist_name = payload.get("playlist_name")

    if not band_names or not playlist_name:
        raise ValueError("band_names and playlist_name are required")

    if isinstance(band_names, str):
        band_names = [band_names]
    band_tuple: Tuple[str, ...] = tuple(band_names)

    copy_last_setlist_threshold = int(payload.get("copy_last_setlist_threshold", 15))
    max_setlist_length = int(payload.get("max_setlist_length", 12))
    no_cache = bool(payload.get("no_cache", True))
    rate_limit = float(payload.get("rate_limit", 1.0))
    create_playlist = bool(payload.get("create_playlist", True))
    force_smart_setlist = payload.get("force_smart_setlist")
    force_smart = bool(force_smart_setlist) if force_smart_setlist is not None else None
    use_fuzzy_search = bool(payload.get("use_fuzzy_search", False))

    spotify_user_creds_present = all(
        (
            os.environ.get("SPOTIFY_REFRESH_TOKEN"),
            os.environ.get("SPOTIFY_USERNAME"),
            os.environ.get("SPOTIFY_REDIRECT_URI"),
        )
    )

    if create_playlist and not spotify_user_creds_present:
        logging.info(
            "Spotify user token missing, switching to preview-only mode for %s",
            playlist_name,
        )
        create_playlist = False

    result = run_playlist_job(
        band_tuple,
        playlist_name,
        copy_last_setlist_threshold,
        max_setlist_length,
        no_cache=no_cache,
        rate_limit=rate_limit,
        use_fuzzy_search=use_fuzzy_search,
        create_playlist=create_playlist,
        force_smart_setlist=force_smart,
    )

    return playlist_result_to_payload(result)


def lambda_handler(event, context):
    if _maybe_enable_debugpy():
        logging.info("Handler file: %s", __file__)
        logging.info("Handler cwd: %s", os.getcwd())
        import debugpy

        debugpy.breakpoint()

    method = _http_method(event)
    if method == "OPTIONS" and ENABLE_CORS:
        return _response(200, {"ok": True})

    headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
    auth = headers.get("authorization", "")

    try:
        payload = _parse_body(event)
    except json.JSONDecodeError:
        return _bad_request("invalid_json_body")

    create_playlist = bool(payload.get("create_playlist", True))
    has_valid_token = (
        auth.startswith("Bearer ") and auth.split(" ", 1)[1] in VALID_TOKENS
    )

    # Let's downgrade request if token is invalid but playlist creation is enabled.
    if create_playlist and not has_valid_token:
        logging.warning("Invalid token: %s", auth)
        create_playlist = False
        payload["create_playlist"] = False

    try:
        result = main_logic(payload)
    except ValueError as e:
        return _bad_request(str(e))
    except Exception:
        logger.exception("Error running main_logic")
        return _response(500, {"error": "internal_error"})

    return _response(200, result)
