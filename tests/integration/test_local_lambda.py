import os
import json
import pytest
import requests


LAMBDA_URL = os.environ.get(
    "LAMBDA_URL",
    "http://localhost:9000/2015-03-31/functions/function/invocations",
)
LAMBDA_TOKEN = os.environ.get("LAMBDA_TOKEN")


@pytest.mark.integration
@pytest.mark.skipif(not LAMBDA_TOKEN, reason="LAMBDA_TOKEN not set for integration test")
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
            }
        ),
        "isBase64Encoded": False,
    }

    resp = requests.post(LAMBDA_URL, json=payload, timeout=15)

    assert resp.status_code == 200
    data = resp.json()
    body = data.get("body")
    inner = json.loads(body) if isinstance(body, str) else body
    assert inner["playlist"]["name"] == "OPETH LAMBDA TEST"
