from flask import Flask, jsonify, request

# ----------------------------------------------------------------------
# NDNx Content Key Cache Service Code
# This service simulates a content key cache that NDNx uses to check if
# it can serve a requested asset. This informs the VPN service what the
# encrypted content key the user device's client software should request for is.
# ----------------------------------------------------------------------

app = Flask(__name__)


# Heartbeat endpoint included on all services for testing deployment status
@app.route("/heartbeat")
def heartbeat():
    """Return a simple OK message for health checks."""
    return jsonify({"status": "ok", "message": "Flask heartbeat OK"}), 200


# The main endpoint of this service simulates a cache hit/miss encounter to check whether
# a given content key is available in the cache. Since the experiment is run with a single
# asset the conditional is hardcoded to return a valid token for the encrypted asset.
@app.route("/content_key")
def check_content_key():
    content_key = request.args.get("content_key")

    if content_key == "10mb.bin":
        return "gAAAAABpNfPVKq01kUouFVsT2PQGo83UWEuWevxB9TjVEz2D1v9Pz2y18QZtohsCpEhHP0GQ6sUYB1Bzcp4-_0akVGeMPLhd4g=="

    return jsonify("Key not found", 500)


if __name__ == "__main__":
    # Listen on all interfaces, port 8000
    app.run(host="0.0.0.0", port=8000)
