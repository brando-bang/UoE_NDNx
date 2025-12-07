import os
import time

import requests
from cryptography.fernet import Fernet
from flask import Flask, jsonify, request

app = Flask(__name__)

CDN_URL = os.getenv("ndnx_qa_cdn_url")
QA_KEY = os.getenv("ndnx_qa_key").encode("utf-8")
crypto_util = Fernet(QA_KEY)


@app.route("/heartbeat")
def heartbeat():
    """Return a simple OK message for health checks."""
    return jsonify({"status": "ok", "message": "Flask heartbeat OK"}), 200


@app.route("/download_direct")
def download_direct():
    target_url = "https://mirror.nforce.com/pub/speedtests/10mb.bin"
    start_time = time.time()

    get(target_url)
    elapsed_time = time.time() - start_time

    return jsonify(str(elapsed_time * 1000) + " milliseconds")


@app.route("/download_cdn")
def download_cdn():
    start_time = time.time()

    get(CDN_URL)
    elapsed_time = time.time() - start_time

    return jsonify(str(elapsed_time * 1000) + " milliseconds")


@app.route("/use_vpn")
def send_request():
    try:
        start_time = time.time()

        target_url = request.args.get("url")
        target_endpoint = request.args.get("endpoint")
        plaintext_vpn_payload_bytes = target_endpoint.encode("utf-8")
        encrypted_vpn_payload_bytes = crypto_util.encrypt(plaintext_vpn_payload_bytes)
        encrypted_vpn_payload = encrypted_vpn_payload_bytes.decode("utf-8")
        vpn_url = target_url + "/use_vpn?vpn_payload=" + encrypted_vpn_payload

        response = requests.get(vpn_url)
        response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)

        encrypted_vpn_response_bytes = response.content
        decrypted_vpn_response_bytes = crypto_util.decrypt(encrypted_vpn_response_bytes)
        decrypted_vpn_response_bytes.decode("utf-8")

        elapsed_time = time.time() - start_time

        return jsonify(str(elapsed_time * 1000) + " milliseconds")
    except requests.exceptions.RequestException as e:
        return jsonify({"error": str(e)}), 500


def get(target_url):
    try:
        headers = {
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        }

        response = requests.get(target_url, headers=headers)
        response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)

        return response.content
    except requests.exceptions.RequestException as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    # Listen on all interfaces, port 8000
    app.run(host="0.0.0.0", port=8000)
