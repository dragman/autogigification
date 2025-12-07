import os
import json
import pytest
import requests


LAMBDA_URL = os.environ.get(
    "LAMBDA_URL",
    "http://localhost:9000/2015-03-31/functions/function/invocations",
)
# Prefer explicit token, fallback to first APP_TOKENS entry so local stacks run without extra env wiring.
_app_tokens = os.environ.get("APP_TOKENS", "")
_app_token_list = [t.strip() for t in _app_tokens.split(",") if t.strip()]
LAMBDA_TOKEN = os.environ.get("LAMBDA_TOKEN") or (_app_token_list[0] if _app_token_list else None)


@pytest.mark.integration
@pytest.mark.skipif(
    not LAMBDA_TOKEN,
    reason="Set LAMBDA_TOKEN or APP_TOKENS to run integration test",
)
def test_local_lambda_invocation():
    payload = {
        "headers": {
            "authorization": f"Bearer {LAMBDA_TOKEN}",
        },
        "body": json.dumps(
            {
                "band_names": ["Opeth"],
                "playlist_name": "OPETH LAMBDA TEST",
                "copy_last_setlist_threshold": 15,
                "max_setlist_length": 12,
                "no_cache": True,
                "create_playlist": False,
            }
        ),
        "isBase64Encoded": False,
    }

    try:
        resp = requests.post(LAMBDA_URL, json=payload, timeout=15)
    except requests.exceptions.RequestException as exc:
        pytest.skip(f"Lambda URL not reachable: {exc}")

    assert resp.status_code == 200
    data = resp.json()
    body = data.get("body")
    inner = json.loads(body) if isinstance(body, str) else body
    assert inner["setlists"]
    assert inner.get("created_playlist") is False
