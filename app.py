# =========================
# app.py
# =========================
import os
import hmac
import hashlib
import json

from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient, ReturnDocument

app = Flask(__name__)
CORS(app)  # allow all origins so your frontend can call the API

# ---- Environment variables ----
MONGO_URI = os.getenv("MONGO_URI")
if not MONGO_URI:
    raise RuntimeError("MONGO_URI is not set in environment variables")

RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET")
if not RAZORPAY_WEBHOOK_SECRET:
    raise RuntimeError("RAZORPAY_WEBHOOK_SECRET is not set in environment variables")

MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "charan")  # default to 'charan' as you said

# ---- MongoDB connection ----
client = MongoClient(MONGO_URI)
db = client[MONGO_DB_NAME]

# You said collection name is "blance"
balance_collection = db["blance"]


def increment_balance():
    """
    Increment the amount field by 1 in a single document.
    If no document exists, create one with amount starting at 1.
    """
    doc = balance_collection.find_one_and_update(
        filter={},
        update={"$inc": {"amount": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return doc.get("amount", 0)


def get_balance():
    """
    Get current amount from the collection.
    If no document exists, return 0.
    """
    doc = balance_collection.find_one({})
    if not doc:
        return 0
    return doc.get("amount", 0)


# ---- Routes ----

@app.route("/balance", methods=["GET"])
def balance():
    """
    Frontend calls this to get the current total number.
    """
    try:
        amount = get_balance()
        return jsonify({"balance": amount})
    except Exception as e:
        print("Error fetching balance:", e)
        return jsonify({"error": "Failed to fetch balance"}), 500


@app.route("/razorpay-webhook", methods=["POST"])
def razorpay_webhook():
    """
    Razorpay sends payment events here.
    We verify the signature and, on payment.captured, increment the number.
    """
    try:
        # Raw request body
        body_bytes = request.data

        # Signature from Razorpay header
        received_signature = request.headers.get("X-Razorpay-Signature")
        if not received_signature:
            return "Missing signature", 400

        # Generate expected signature
        generated_signature = hmac.new(
            RAZORPAY_WEBHOOK_SECRET.encode("utf-8"),
            body_bytes,
            hashlib.sha256,
        ).hexdigest()

        if generated_signature != received_signature:
            print("Invalid webhook signature")
            return "Invalid signature", 400

        # Parse payload
        try:
            payload = json.loads(body_bytes.decode("utf-8"))
        except json.JSONDecodeError:
            return "Invalid JSON", 400

        event = payload.get("event")
        if event == "payment.captured":
            try:
                new_amount = increment_balance()
                print("Balance Updated:", new_amount)
            except Exception as e:
                print("Error updating balance:", e)
                # Still return success so Razorpay doesn't retry forever

        return jsonify({"success": True})

    except Exception as e:
        print("Unexpected error in webhook:", e)
        return "Server error", 500


if __name__ == "__main__":
    # For local testing only; Render will use gunicorn
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
