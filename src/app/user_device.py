import requests
import time
import zipfile
from io import BytesIO
from flask import Flask, jsonify, request

app = Flask(__name__)


@app.route("/heartbeat")
def heartbeat():
    """Return a simple OK message for health checks."""
    return jsonify({"status": "ok", "message": "Flask heartbeat OK"}), 200


@app.route("/download_direct")
def download_direct():
    target_url = "https://github.com/twbs/bootstrap/archive/v4.4.1.zip"

    try:
        start_time = time.time()
        response = requests.get(target_url)
        response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)

        _zip = BytesIO(response.content)

        with zipfile.ZipFile(_zip, 'r') as zf:
            files = []

            for name in zf.namelist():
                try:
                    file_content = zf.read(name).decode('cp437')
                    files.append(file_content)
                except KeyError:
                    print(name + " not found in the archive.")

            jsonify(files)

            elapsed_time = time.time() - start_time

            return jsonify(str(elapsed_time*1000) + " milliseconds")
    except requests.exceptions.RequestException as e:
        return jsonify({"error": str(e)}), 500

@app.route("/download_cdn")
def download_cdn():
    target_url = "https://cdn.jsdelivr.net/npm/bootstrap@4.4.1/dist/js/bootstrap.min.js"
    start_time = time.time()

    get(target_url)
    elapsed_time = time.time() - start_time

    return jsonify(str(elapsed_time * 1000) + " milliseconds")


@app.route("/send_request")
def send_request():
    target_url = request.args.get("target_url")

    try:
        response = requests.get(target_url)
        response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
        data = response.json()
        return jsonify(data)
    except requests.exceptions.RequestException as e:
        return jsonify({"error": str(e)}), 500


def get(target_url):
    try:
        response = requests.get(target_url)
        response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
        data = response.json()
        return jsonify(data)
    except requests.exceptions.RequestException as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    # Listen on all interfaces, port 8000
    app.run(host="0.0.0.0", port=8000)
