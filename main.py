import os
import json
from fastapi import FastAPI, Depends, HTTPException, Header
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware

import firebase_admin
from firebase_admin import credentials, auth, db

# ------------------------
# ENV
# ------------------------
load_dotenv()

ADMIN_UIDS = [
    uid.strip()
    for uid in os.getenv("ADMIN_UIDS", "").split(",")
    if uid.strip()
]

FIREBASE_ADMIN_JSON = os.getenv("FIREBASE_ADMIN_JSON")
FIREBASE_DB_URL = os.getenv("FIREBASE_DB_URL")

if not ADMIN_UIDS:
    raise RuntimeError("ADMIN_UIDS is missing or empty")

if not FIREBASE_ADMIN_JSON or not FIREBASE_DB_URL:
    raise RuntimeError("Missing Firebase environment variables")

# ------------------------
# FIREBASE INIT (ENV BASED)
# ------------------------
cred = credentials.Certificate(json.loads(FIREBASE_ADMIN_JSON))

firebase_admin.initialize_app(
    cred,
    {"databaseURL": FIREBASE_DB_URL}
)

database = db.reference("/")

# ------------------------
# FASTAPI APP
# ------------------------
app = FastAPI(title="CA Portfolio API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        # add production frontend later
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------
# AUTH DEPENDENCY
# ------------------------
def verify_admin(authorization: str = Header(...)):
    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            raise ValueError("Invalid auth scheme")

        decoded = auth.verify_id_token(token)

        if decoded.get("uid") not in ADMIN_UIDS:
            raise PermissionError("Not an admin")

        return decoded

    except Exception:
        raise HTTPException(
            status_code=401,
            detail="Unauthorized"
        )

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
        "email": user.get("email"),
    }
