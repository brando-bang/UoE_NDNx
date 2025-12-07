import os

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
    headers = {
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0",
    }

    target_url = "https://mirror.nforce.com/pub/speedtests/10mb.bin"
    return get(target_url)


@app.route("/download_cdn")
def download_cdn():
    return get(CDN_URL)


@app.route("/use_vpn")
def use_vpn():
    encrypted_vpn_payload = request.args.get("vpn_payload")
    encrypted_vpn_payload_bytes = encrypted_vpn_payload.encode("utf-8")
    decrypted_vpn_payload_bytes = crypto_util.decrypt(encrypted_vpn_payload_bytes)
    decrypted_vpn_payload = decrypted_vpn_payload_bytes.decode("utf-8")

    data = None

    if decrypted_vpn_payload == "direct":
        data = download_direct()
    elif decrypted_vpn_payload == "cdn":
        data = download_cdn()
    if not data:
        return jsonify("no data found", 500)

    encrypted_data = crypto_util.encrypt(data)
    encrypted_vpn_response = encrypted_data.decode("utf-8")

    return encrypted_vpn_response


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
        print(e)
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    # Listen on all interfaces, port 8000
    app.run(host="0.0.0.0", port=8000)
