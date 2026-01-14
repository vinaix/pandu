import os, json, uuid
from fastapi import FastAPI, Depends, HTTPException, Header, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from supabase import create_client
import firebase_admin
from firebase_admin import credentials, auth

# ------------------------
# ENV
# ------------------------
load_dotenv()

ADMIN_UIDS = [u.strip() for u in os.getenv("ADMIN_UIDS","").split(",") if u.strip()]
FIREBASE_ADMIN_JSON = os.getenv("FIREBASE_ADMIN_JSON")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

if not ADMIN_UIDS or not FIREBASE_ADMIN_JSON or not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    raise RuntimeError("Missing env vars")

# ------------------------
# FIREBASE AUTH ONLY
# ------------------------
cred = credentials.Certificate(json.loads(FIREBASE_ADMIN_JSON))
firebase_admin.initialize_app(cred)

# ------------------------
# SUPABASE
# ------------------------
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# ------------------------
# APP
# ------------------------
app = FastAPI(title="CA Portfolio API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------
# AUTH
# ------------------------
def verify_admin(authorization: str = Header(...)):
    try:
        token = authorization.split()[1]
        decoded = auth.verify_id_token(token)
        if decoded["uid"] not in ADMIN_UIDS:
            raise Exception()
        return decoded
    except Exception:
        raise HTTPException(status_code=401, detail="Unauthorized")

# ------------------------
# FILE UPLOAD (PDF / EXCEL / PPT)
# ------------------------
@app.post("/admin/upload")
def upload_file(
    section: str,
    file: UploadFile = File(...),
    user=Depends(verify_admin)
):
    file_id = str(uuid.uuid4())
    path = f"{file_id}-{file.filename}"

    supabase.storage.from_(section).upload(
        path,
        file.file,
        {"content-type": file.content_type}
    )

    public_url = supabase.storage.from_(section).get_public_url(path)

    return {"file_url": public_url}

# ------------------------
# CREATE ENTRY
# ------------------------
@app.post("/admin/entry")
def create_entry(
    data: dict,
    user=Depends(verify_admin)
):
    data["id"] = str(uuid.uuid4())
    supabase.table("entries").insert(data).execute()
    return {"status": "created"}

# ------------------------
# PUBLIC READ
# ------------------------
@app.get("/entries/{section}")
def get_entries(section: str):
    return supabase.table("entries").select("*").eq("section_key", section).execute().data
