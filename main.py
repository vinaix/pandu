import os
import json
from fastapi import FastAPI, Depends, HTTPException, Header
from dotenv import load_dotenv

import firebase_admin
from firebase_admin import credentials, auth, db

# ------------------------
# ENV
# ------------------------
load_dotenv()

ADMIN_UID = os.getenv("ADMIN_UID")
FIREBASE_ADMIN_JSON = os.getenv("FIREBASE_ADMIN_JSON")
FIREBASE_DB_URL = os.getenv("FIREBASE_DB_URL")

if not ADMIN_UID or not FIREBASE_ADMIN_JSON or not FIREBASE_DB_URL:
    raise RuntimeError("Missing required environment variables")

# ------------------------
# FIREBASE INIT (ENV BASED)
# ------------------------
cred = credentials.Certificate(json.loads(FIREBASE_ADMIN_JSON))

firebase_admin.initialize_app(cred, {
    "databaseURL": FIREBASE_DB_URL
})

database = db.reference("/")

# ------------------------
# FASTAPI APP
# ------------------------
app = FastAPI(title="CA Portfolio API")

# ------------------------
# AUTH DEPENDENCY
# ------------------------
def verify_admin(authorization: str = Header(...)):
    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            raise Exception()

        decoded = auth.verify_id_token(token)

        if decoded["uid"] != ADMIN_UID:
            raise Exception()

        return decoded

    except Exception:
        raise HTTPException(status_code=401, detail="Unauthorized")

# ------------------------
# HEALTH CHECK
# ------------------------
@app.get("/")
def health():
    return {"status": "running"}

# ------------------------
# ADMIN TEST ENDPOINT
# ------------------------
@app.get("/admin/test")
def admin_test(user=Depends(verify_admin)):
    return {
        "message": "Admin access granted",
        "uid": user["uid"],
        "email": user.get("email")
    }
