import time
import zipfile
from io import BytesIO

import requests
from flask import Flask, jsonify, request

app = Flask(__name__)


@app.route("/heartbeat")
def heartbeat():
    """Return a simple OK message for health checks."""
    return jsonify({"status": "ok", "message": "Flask heartbeat OK"}), 200


@app.route("/download_direct")
def download_direct():
    target_url = "https://raw.githubusercontent.com/twbs/bootstrap/refs/heads/main/dist/js/bootstrap.min.js"
    start_time = time.time()

    get(target_url)
    elapsed_time = time.time() - start_time

    return jsonify(str(elapsed_time * 1000) + " milliseconds")


@app.route("/download_cdn")
def download_cdn():
    target_url = (
        "https://cdnjs.cloudflare.com/ajax/libs/bootstrap/5.3.8/js/bootstrap.min.js"
    )
    start_time = time.time()

    get(target_url)
    elapsed_time = time.time() - start_time

    return jsonify(str(elapsed_time * 1000) + " milliseconds")


@app.route("/download_vpn")
def send_request():
    target_url = request.args.get("target_url")

    try:
        start_time = time.time()

        response = requests.get(target_url)
        response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)

        elapsed_time = time.time() - start_time

        return jsonify(str(elapsed_time * 1000) + " milliseconds")
    except requests.exceptions.RequestException as e:
        return jsonify({"error": str(e)}), 500


def get(target_url):
    try:
        response = requests.get(target_url)
        response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)

        return response.content
    except requests.exceptions.RequestException as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    # Listen on all interfaces, port 8000
    app.run(host="0.0.0.0", port=8000)
