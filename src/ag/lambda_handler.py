"""AWS Lambda entry point for creating Spotify playlists."""

import base64
import json
import logging
import os
from typing import Any, Dict, Tuple

from dotenv import load_dotenv

from ag.run import run_playlist_job

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Load environment variables (client IDs, secrets, etc.) when running outside AWS config.
load_dotenv()

ENABLE_CORS = os.environ.get("ENABLE_CORS", "").lower() in {"1", "true", "yes"}

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

    playlist = run_playlist_job(
        band_tuple,
        playlist_name,
        copy_last_setlist_threshold,
        max_setlist_length,
        no_cache=no_cache,
        rate_limit=rate_limit,
    )

    return {"playlist": {"name": playlist.name, "id": playlist.id, "url": playlist.url}}


def lambda_handler(event, context):
    method = _http_method(event)
    if method == "OPTIONS" and ENABLE_CORS:
        return _response(200, {"ok": True})

    headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
    auth = headers.get("authorization", "")

    if not auth.startswith("Bearer "):
        return _unauthorized("missing_or_invalid_authorization_header")

    token = auth.split(" ", 1)[1]
    if token not in VALID_TOKENS:
        return _unauthorized("invalid_token")

    try:
        payload = _parse_body(event)
    except json.JSONDecodeError:
        return _bad_request("invalid_json_body")

    try:
        result = main_logic(payload)
    except ValueError as e:
        return _bad_request(str(e))
    except Exception:
        logger.exception("Error running main_logic")
        return _response(500, {"error": "internal_error"})

    return _response(200, result)
