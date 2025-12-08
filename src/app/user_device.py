import os
import time
from urllib.parse import quote_plus

import requests
from cryptography.fernet import Fernet
from flask import Flask, jsonify, request

# ----------------------------------------------------------------------
# User Device Service Code
# This service simulates a user device that can run VPN client software
# with optional NDNx functionality. It can request to download an asset
# directly from a host server, from a CDN, directly from the host over VPN,
# through a CDN over VPN, or using NDNx.
# For the purpose of the NDNx research project, the endpoint for each internet
# strategy also times the download for comparing relative performance.
# ----------------------------------------------------------------------

app = Flask(__name__)

# These constants are required for the VPN e2ee and are passed to the
# server during deployment in the cdk.py file.
ASSET_KEY = os.getenv("ndnx_asset_key").encode("utf-8")
CDN_URL = os.getenv("ndnx_qa_cdn_url")
CONTENT_KEY = os.getenv("ndnx_content_key").encode("utf-8")
NDNX_CONTENT_CACHE = os.getenv("ndnx_qa_content_cache")
QA_KEY = os.getenv("ndnx_qa_key").encode("utf-8")

# creates encrypt/decrypt utils for each specific key
asset_crypto_util = Fernet(ASSET_KEY)
content_key_crypto_util = Fernet(CONTENT_KEY)
vpn_crypto_util = Fernet(QA_KEY)

# Heartbeat endpoint included on all services for testing deployment status


@app.route("/heartbeat")
def heartbeat():
    """Return a simple OK message for health checks."""
    return jsonify({"status": "ok", "message": "Flask heartbeat OK"}), 200


# Requests the asset directly from the host server
@app.route("/download_direct")
def download_direct():
    target_url = "https://mirror.nforce.com/pub/speedtests/10mb.bin"
    start_time = time.time()

    get(target_url)
    elapsed_time = time.time() - start_time

    return jsonify(str(elapsed_time * 1000) + " milliseconds")


# Requests the asset from a CDN service.
@app.route("/download_cdn")
def download_cdn():
    start_time = time.time()

    get(CDN_URL + "10mb.bin")
    elapsed_time = time.time() - start_time

    return jsonify(str(elapsed_time * 1000) + " milliseconds")


# Encrypts and forwards the request for the asset to the VPN service. Request
# params are used to determine whether the VPN will consequently request the
# asset directly from the host or from a CDN.
@app.route("/use_vpn")
def send_request():
    try:
        start_time = time.time()

        # Get parameters from the request
        target_url = request.args.get("url")
        target_endpoint = request.args.get("endpoint")

        # Encrypt the VPN payload (the target endpoint)
        plaintext_vpn_payload_bytes = target_endpoint.encode("utf-8")
        encrypted_vpn_payload_bytes = vpn_crypto_util.encrypt(
            plaintext_vpn_payload_bytes
        )
        encrypted_vpn_payload = encrypted_vpn_payload_bytes.decode("utf-8")

        # Send the request to the VPN service
        vpn_url = f"{target_url}/use_vpn?vpn_payload={encrypted_vpn_payload}"
        response = requests.get(vpn_url)
        response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)

        # Decrypt the VPN response
        encrypted_vpn_response_bytes = response.content
        decrypted_vpn_response_bytes = vpn_crypto_util.decrypt(
            encrypted_vpn_response_bytes
        )
        decrypted_vpn_response_bytes.decode("utf-8")

        elapsed_time = time.time() - start_time

        # Return elapsed time
        return jsonify(str(elapsed_time * 1000) + " milliseconds")
    except requests.exceptions.RequestException as e:
        return jsonify({"error": str(e)}), 500


# Sends a request to the VPN service while employig NDNx techniques to retrieve
# the asset's content encrypted from a VPN-managed geographically local cache node.
@app.route("/use_ndnx")
def use_ndnx():
    try:
        start_time = time.time()

        # Get parameters from the request
        target_url = request.args.get("url")
        content_key = request.args.get("content_key")

        # Encrypt the content key and escape it for URL param usage
        encrypted_content_key = content_key_crypto_util.encrypt(
            content_key.encode("utf-8")
        ).decode("utf-8")
        content_key_query_param = quote_plus(encrypted_content_key)

        # Send the NDNx request to the VPN service for the encrypted content key for the encrypted asset
        encrypted_ndnx_content_key = get(
            f"{target_url}/use_ndnx?content_key={content_key_query_param}"
        )

        # Decrypt the e2ee response for the still-encrypted key
        ndnx_content_key = vpn_crypto_util.decrypt(encrypted_ndnx_content_key).decode(
            "utf-8"
        )

        # Retrieve the encrypted asset from the VPN-managed CDN to complete the NDNx exchange.
        encrypted_asset = get(CDN_URL + ndnx_content_key)

        # Decrypt the asset - it is never in plaintext until it is in the user device's memory
        asset_crypto_util.decrypt(encrypted_asset)

        elapsed_time = time.time() - start_time

        # Return elapsed time
        return jsonify(str(elapsed_time * 1000) + " milliseconds")
    except requests.exceptions.RequestException as e:
        return jsonify({"error": str(e)}), 500


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
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    # Listen on all interfaces, port 8000
    app.run(host="0.0.0.0", port=8000)
