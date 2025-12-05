import importlib
import json

import pytest


def load_lambda_handler(monkeypatch, tokens="valid-token"):
    monkeypatch.setenv("APP_TOKENS", tokens)
    from ag import lambda_handler

    importlib.reload(lambda_handler)
    return lambda_handler


def test_lambda_handler_requires_authorization_header(monkeypatch):
    lh = load_lambda_handler(monkeypatch)
    event = {"headers": {}}

    resp = lh.lambda_handler(event, None)

    assert resp["statusCode"] == 401
    assert "missing_or_invalid_authorization_header" in resp["body"]


def test_lambda_handler_rejects_invalid_token(monkeypatch):
    lh = load_lambda_handler(monkeypatch)
    event = {"headers": {"Authorization": "Bearer wrong"}}

    resp = lh.lambda_handler(event, None)

    assert resp["statusCode"] == 401
    assert "invalid_token" in resp["body"]


def test_lambda_handler_handles_invalid_json(monkeypatch):
    lh = load_lambda_handler(monkeypatch)
    event = {
        "headers": {"Authorization": "Bearer valid-token"},
        "body": "{bad json",
    }

    resp = lh.lambda_handler(event, None)

    assert resp["statusCode"] == 400
    assert "invalid_json_body" in resp["body"]


def test_lambda_handler_success_path(monkeypatch):
    """
    Example JSON payload:

    {
        "band_names": ["Band"],
        "playlist_name": "Playlist",
        "copy_last_setlist_threshold": 15,
        "max_setlist_length": 12,
        "no_cache": true
    }
    """

    lh = load_lambda_handler(monkeypatch)

    def fake_main_logic(payload):
        return {"ok": True, "payload": payload}

    monkeypatch.setattr(lh, "main_logic", fake_main_logic)

    payload = {"band_names": ["Band"], "playlist_name": "Playlist"}
    event = {
        "headers": {"Authorization": "Bearer valid-token"},
        "body": json.dumps(payload),
    }

    resp = lh.lambda_handler(event, None)

    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["ok"] is True
    assert body["payload"] == payload


def test_lambda_handler_full_payload_example(monkeypatch):
    """Example of a full request payload you can use in Lambda tests."""
    lh = load_lambda_handler(monkeypatch)

    # Stub out the heavy work; in a real integration test you'd let this run.
    def fake_main_logic(payload):
        return {
            "playlist": {
                "name": payload["playlist_name"],
                "id": "123",
                "url": "http://example",
            }
        }

    monkeypatch.setattr(lh, "main_logic", fake_main_logic)

    payload = {
        "band_names": ["BandA", "BandB"],
        "playlist_name": "My Lambda Playlist",
        "copy_last_setlist_threshold": 10,
        "max_setlist_length": 12,
        "no_cache": True,
        "rate_limit": 0.5,
    }

    event = {
        "headers": {"Authorization": "Bearer valid-token"},
        "body": json.dumps(payload),
        "isBase64Encoded": False,
    }

    resp = lh.lambda_handler(event, None)

    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["playlist"]["name"] == "My Lambda Playlist"
