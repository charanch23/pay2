import os
import hmac
import hashlib
import json

from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient, ReturnDocument

app = Flask(__name__)
CORS(app)

# -------------------------------
# Environment Variables
# -------------------------------
MONGO_URI = os.getenv("MONGO_URI")
if not MONGO_URI:
    raise RuntimeError("MONGO_URI is missing. Set it in Render environment variables.")

RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET")
if not RAZORPAY_WEBHOOK_SECRET:
    raise RuntimeError("RAZORPAY_WEBHOOK_SECRET is missing. Set it in Render environment variables.")

# Database name = 'charan' (you told)
MONGO_DB_NAME = "charan"

# Collection name = 'blance' (you told)
COLLECTION_NAME = "blance"

# -------------------------------
# MongoDB Connection
# -------------------------------
client = MongoClient(MONGO_URI)
db = client[MONGO_DB_NAME]
balance_collection = db[COLLECTION_NAME]


def increment_balance():
    """Increase amount by 1. Create document if not exists."""
    doc = balance_collection.find_one_and_update(
        filter={},
        update={"$inc": {"amount": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER
    )
    return doc.get("amount", 0)


def get_balance():
    """Return current balance amount."""
    doc = balance_collection.find_one({})
    if not doc:
        return 0
    return doc.get("amount", 0)


# -------------------------------
# Routes
# -------------------------------

@app.route("/balance", methods=["GET"])
def balance():
    """Frontend fetches updated number."""
    try:
        amount = get_balance()
        return jsonify({"balance": amount})
    except Exception as e:
        print("Error fetching balance:", e)
        return jsonify({"error": "Failed to fetch balance"}), 500


@app.route("/razorpay-webhook", methods=["POST"])
def razorpay_webhook():
    """Razorpay sends successful payment events here."""
    try:
        body = request.data
        received_signature = request.headers.get("X-Razorpay-Signature")

        if not received_signature:
            return "Signature missing", 400

        # Verify signature
        generated_signature = hmac.new(
            RAZORPAY_WEBHOOK_SECRET.encode("utf-8"),
            body,
            hashlib.sha256
        ).hexdigest()

        if generated_signature != received_signature:
            print("Invalid Signature")
            return "Invalid signature", 400

        # Parse JSON payload
        payload = json.loads(body.decode("utf-8"))
        event = payload.get("event")

        if event == "payment.captured":
            new_amount = increment_balance()
            print("Balance Updated:", new_amount)

        return jsonify({"success": True})

    except Exception as e:
        print("Webhook error:", e)
        return "Server Error", 500


# -------------------------------
# Local run (Render uses gunicorn)
# -------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
