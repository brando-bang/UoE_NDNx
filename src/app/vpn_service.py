import os
from urllib.parse import quote_plus

import requests
from cryptography.fernet import Fernet
from flask import Flask, jsonify, request

# ----------------------------------------------------------------------
# VPN Service Code
# This service simulates the VPN server that forwards requests from the
# User Device to ensure e2ee transmission of user traffic. It can forward
# requests to download an asset directly from a host server, from a CDN,
# or retrieve an NDNx content key from the content key cache.
# ----------------------------------------------------------------------

app = Flask(__name__)

# These constants are required for the VPN e2ee and are passed to the
# server during deployment in the cdk.py file.
CDN_URL = os.getenv("ndnx_qa_cdn_url")
CONTENT_KEY = os.getenv("ndnx_content_key").encode("utf-8")
CONTENT_KEY_CACHE = os.getenv("ndnx_content_key_cache")
QA_KEY = os.getenv("ndnx_qa_key").encode("utf-8")

# creates encrypt/decrypt utils for each specific key
content_key_crypto_util = Fernet(CONTENT_KEY)
vpn_crypto_util = Fernet(QA_KEY)


# Heartbeat endpoint included on all services for testing deployment status
@app.route("/heartbeat")
def heartbeat():
    """Return a simple OK message for health checks."""
    return jsonify({"status": "ok", "message": "Flask heartbeat OK"}), 200


# Requests the asset directly from the host server
def download_direct():
    target_url = "https://mirror.nforce.com/pub/speedtests/10mb.bin"
    return get(target_url)


# Requests the asset from a CDN service.


def download_cdn():
    return get(CDN_URL + "10mb.bin")


# The main endpoint for the VPN service to handle user requests.
# User requests are decrypted and then forwarded to the appropriate
# downstream service. The response is then encrypted and returned
@app.route("/use_vpn")
def use_vpn():
    encrypted_vpn_payload = request.args.get("vpn_payload")
    encrypted_vpn_payload_bytes = encrypted_vpn_payload.encode("utf-8")
    decrypted_vpn_payload_bytes = vpn_crypto_util.decrypt(encrypted_vpn_payload_bytes)
    decrypted_vpn_payload = decrypted_vpn_payload_bytes.decode("utf-8")

    data = None

    if decrypted_vpn_payload == "direct":
        data = download_direct()
    elif decrypted_vpn_payload == "cdn":
        data = download_cdn()
    if not data:
        return jsonify("no data found", 500)

    encrypted_data = vpn_crypto_util.encrypt(data)
    encrypted_vpn_response = encrypted_data.decode("utf-8")

    return encrypted_vpn_response


# This endpoint handles NDNx requests from the user device. The requested content key is
# decrypted and then checked in the content key cache to determine what the encrypted key
# that should be requested by the user is. The encrypted key is also re-encrypted with the
# VPN - client shared key in-line with the rest of the VPN service's e2ee responses.
@app.route("/use_ndnx")
def use_ndnx():
    encrypted_content_key = request.args.get("content_key")
    content_key = content_key_crypto_util.decrypt(encrypted_content_key).decode("utf-8")

    content_key_query_param = quote_plus(content_key)

    ndnx_content_key = get(
        f"http://{CONTENT_KEY_CACHE}:8000/content_key?content_key={content_key_query_param}"
    )

    return vpn_crypto_util.encrypt(ndnx_content_key).decode("utf-8")


# Helper tool for making GET requests
def get(target_url):
    try:
        # Headers prevent caching to ensure integrity of timing results
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
