from datetime import datetime, timezone
import hashlib
from flask import Flask, request, jsonify
from flask_cors import CORS
from pydantic import ValidationError
from models import SurveySubmission, StoredSurveyRecord
from storage import append_json_line

app = Flask(__name__)
CORS(app, resources={r"/v1/*": {"origins": "*"}})

# -----------------------
# Helper functions
# -----------------------
def hash_value(value: str) -> str:
    """Return SHA-256 hash of the input string."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()

def compute_submission_id(email: str) -> str:
    """Generate submission_id as SHA-256(email + YYYYMMDDHH)."""
    now = datetime.utcnow().strftime("%Y%m%d%H")
    return hash_value(email + now)

# -----------------------
# Routes
# -----------------------
@app.route("/ping", methods=["GET"])
def ping():
    """Simple health check endpoint."""
    return jsonify({
        "status": "ok",
        "message": "API is alive",
        "utc_time": datetime.now(timezone.utc).isoformat()
    })

@app.post("/v1/survey")
def submit_survey():
    payload = request.get_json(silent=True)
    if payload is None:
        return jsonify({"error": "invalid_json", "detail": "Body must be application/json"}), 400

    try:
        submission = SurveySubmission(**payload)
    except ValidationError as ve:
        return jsonify({"error": "validation_error", "detail": ve.errors()}), 422

    # Hash PII
    hashed_email = hash_value(submission.email)
    hashed_age = hash_value(str(submission.age))

    # Determine submission_id
    submission_id = submission.submission_id or compute_submission_id(submission.email)

    # Build the stored record
    record = StoredSurveyRecord(
        name=submission.name,
        email=hashed_email,
        age=hashed_age,
        consent=submission.consent,
        rating=submission.rating,
        comments=submission.comments,
        user_agent=submission.user_agent,
        submission_id=submission_id,
        received_at=datetime.now(timezone.utc),
        ip=request.headers.get("X-Forwarded-For", request.remote_addr or "")
    )

    append_json_line(record.dict())
    return jsonify({"status": "ok", "submission_id": submission_id}), 201
# -----------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
