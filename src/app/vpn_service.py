import zipfile
from io import BytesIO

import requests
from flask import Flask, jsonify

app = Flask(__name__)


@app.route("/heartbeat")
def heartbeat():
    """Return a simple OK message for health checks."""
    return jsonify({"status": "ok", "message": "Flask heartbeat OK"}), 200


@app.route("/download_direct")
def download_direct():
    target_url = "https://raw.githubusercontent.com/twbs/bootstrap/refs/heads/main/dist/js/bootstrap.min.js"

    return get(target_url)


@app.route("/download_cdn")
def download_cdn():
    target_url = (
        "https://cdnjs.cloudflare.com/ajax/libs/bootstrap/5.3.8/js/bootstrap.min.js"
    )

    return get(target_url)


def get(target_url):
    try:
        response = requests.get(target_url)
        response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)

        return response.content
    except requests.exceptions.RequestException as e:
        print(e)
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    # Listen on all interfaces, port 8000
    app.run(host="0.0.0.0", port=8000)
