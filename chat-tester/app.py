"""
Flask chat UI for testing deployed ADK agents on Cloud Run (or anywhere else
running an ADK api_server/web endpoint).

Customizable at runtime -- no restart needed to point at a different
deployed agent. Enter the target's URL and app name in the top bar and
click "Connect", similar to switching the request URL in an API client
like Bruno/Postman.

Usage:
    pip install -r requirements.txt
    python app.py

Then open http://127.0.0.1:5000
"""
import json
import os
import time
import uuid

import requests
from flask import Flask, jsonify, render_template, request, session

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-only-not-secret")

SAVED_REQUESTS_FILE = os.path.join(os.path.dirname(__file__), "requests.json")

# Only used to pre-fill the UI on first load. The actual target can be
# changed at runtime via the "Connect" bar without restarting this app.
DEFAULT_AGENT_URL = os.environ.get(
    "AGENT_URL", "https://test-app-962412240887.us-east1.run.app"
)
DEFAULT_APP_NAME = os.environ.get("AGENT_APP_NAME", "test_app")


def current_target():
    """Return (agent_url, app_name) for the active connection, or (None,
    None) if nothing has been connected yet this browser session."""
    return session.get("agent_url"), session.get("app_name")


@app.route("/")
def index():
    return render_template(
        "index.html",
        default_agent_url=DEFAULT_AGENT_URL,
        default_app_name=DEFAULT_APP_NAME,
        connected=bool(session.get("agent_url")),
        agent_url=session.get("agent_url", ""),
        app_name=session.get("app_name", ""),
    )


@app.route("/api/list-apps", methods=["POST"])
def list_apps():
    """Proxy: query {url}/list-apps on the target. Requests are made
    server-side so the browser never needs a cross-origin request to the
    target agent (sidesteps CORS entirely)."""
    url = (request.get_json(silent=True) or {}).get("url", "").strip().rstrip("/")
    if not url:
        return jsonify({"error": "Missing url"}), 400
    try:
        resp = requests.get(f"{url}/list-apps", timeout=15)
        resp.raise_for_status()
        return jsonify({"apps": resp.json()})
    except requests.RequestException as exc:
        return jsonify({"error": str(exc)}), 502


@app.route("/api/connect", methods=["POST"])
def connect():
    """Point this tester at a (possibly new) deployed agent and open a
    fresh ADK session against it."""
    data = request.get_json(silent=True) or {}
    url = data.get("agent_url", "").strip().rstrip("/")
    app_name = data.get("app_name", "").strip()

    if not url or not app_name:
        return jsonify({"error": "agent_url and app_name are required"}), 400

    user_id = f"flask-user-{uuid.uuid4().hex[:8]}"
    session_id = f"flask-session-{uuid.uuid4().hex[:8]}"

    try:
        resp = requests.post(
            f"{url}/apps/{app_name}/users/{user_id}/sessions/{session_id}",
            json={},
            timeout=30,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        return jsonify({"error": f"Could not create session at target: {exc}"}), 502

    session["agent_url"] = url
    session["app_name"] = app_name
    session["user_id"] = user_id
    session["session_id"] = session_id

    return jsonify(
        {
            "status": "connected",
            "agent_url": url,
            "app_name": app_name,
            "user_id": user_id,
            "session_id": session_id,
        }
    )


@app.route("/api/new-session", methods=["POST"])
def new_session():
    """Start a fresh conversation against the currently connected target
    (does not change agent_url/app_name)."""
    url, app_name = current_target()
    if not url or not app_name:
        return jsonify({"error": "Not connected to any agent yet"}), 400

    user_id = f"flask-user-{uuid.uuid4().hex[:8]}"
    session_id = f"flask-session-{uuid.uuid4().hex[:8]}"

    try:
        resp = requests.post(
            f"{url}/apps/{app_name}/users/{user_id}/sessions/{session_id}",
            json={},
            timeout=30,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        return jsonify({"error": f"Could not create session at target: {exc}"}), 502

    session["user_id"] = user_id
    session["session_id"] = session_id
    return jsonify({"user_id": user_id, "session_id": session_id})


@app.route("/api/chat", methods=["POST"])
def chat():
    url, app_name = current_target()
    if not url or not app_name:
        return jsonify({"error": "Not connected to any agent yet"}), 400

    user_id = session.get("user_id")
    session_id = session.get("session_id")
    message = (request.get_json(silent=True) or {}).get("message", "").strip()
    if not message:
        return jsonify({"error": "Empty message"}), 400

    payload = {
        "appName": app_name,
        "userId": user_id,
        "sessionId": session_id,
        "newMessage": {
            "role": "user",
            "parts": [{"text": message}],
        },
    }

    try:
        resp = requests.post(f"{url}/run", json=payload, timeout=60)
        resp.raise_for_status()
    except requests.RequestException as exc:
        return jsonify({"error": f"Agent request failed: {exc}"}), 502

    events = resp.json()

    # Concatenate model text parts; collect any Google Search grounding sources.
    reply_text = ""
    sources = []
    for event in events:
        content = event.get("content", {})
        if content.get("role") != "model":
            continue
        for part in content.get("parts", []):
            if "text" in part:
                reply_text += part["text"]
        grounding = event.get("groundingMetadata") or {}
        for chunk in grounding.get("groundingChunks", []):
            web = chunk.get("web", {})
            if web.get("uri"):
                sources.append(
                    {"title": web.get("title", web.get("domain", "source")), "uri": web["uri"]}
                )

    return jsonify(
        {
            "reply": reply_text or "(no text response)",
            "sources": sources,
            "raw_event_count": len(events),
        }
    )


@app.route("/api/saved-requests")
def saved_requests():
    """Serve requests.json (if present) so the Raw Request UI can offer a
    'load a saved request' dropdown. Missing file -> empty list, not an
    error, so the tool still works without it."""
    if not os.path.exists(SAVED_REQUESTS_FILE):
        return jsonify({"requests": []})
    try:
        with open(SAVED_REQUESTS_FILE, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as exc:
        return jsonify({"error": f"Could not read requests.json: {exc}"}), 500
    return jsonify({"requests": data.get("requests", [])})


@app.route("/api/raw-request", methods=["POST"])
def raw_request():
    """Generic HTTP request proxy -- a minimal Bruno/Postman-style "send any
    request" mode. Runs server-side so arbitrary target APIs never need to
    grant this browser CORS access."""
    data = request.get_json(silent=True) or {}
    method = (data.get("method") or "GET").upper()
    url = (data.get("url") or "").strip()
    headers = data.get("headers") or {}
    body = data.get("body")

    if not url:
        return jsonify({"error": "Missing url"}), 400

    kwargs = {"headers": headers, "timeout": 60}
    if body:
        kwargs["data"] = body.encode("utf-8")

    start = time.monotonic()
    try:
        resp = requests.request(method, url, **kwargs)
    except requests.RequestException as exc:
        return jsonify({"error": str(exc)}), 502
    elapsed_ms = round((time.monotonic() - start) * 1000)

    try:
        parsed_body = resp.json()
        body_is_json = True
    except ValueError:
        parsed_body = resp.text
        body_is_json = False

    return jsonify(
        {
            "status_code": resp.status_code,
            "reason": resp.reason,
            "elapsed_ms": elapsed_ms,
            "size_bytes": len(resp.content),
            "headers": dict(resp.headers),
            "body": parsed_body,
            "body_is_json": body_is_json,
        }
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
