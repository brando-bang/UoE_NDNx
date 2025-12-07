import requests
from cryptography.fernet import Fernet
from flask import Flask, jsonify, request

app = Flask(__name__)

QA_KEY = "3p-Y39tgkAs6HJzIJto4gBUwLCEanFjK2qUzTfSsOxQ=".encode("utf-8")
crypto_util = Fernet(QA_KEY)


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
        response = requests.get(target_url)
        response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)

        return response.content
    except requests.exceptions.RequestException as e:
        print(e)
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    # Listen on all interfaces, port 8000
    app.run(host="0.0.0.0", port=8000)
