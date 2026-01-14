import os, json, uuid, datetime
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

ADMIN_UIDS = [u.strip() for u in os.getenv("ADMIN_UIDS", "").split(",") if u.strip()]
FIREBASE_ADMIN_JSON = os.getenv("FIREBASE_ADMIN_JSON")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

if not ADMIN_UIDS or not FIREBASE_ADMIN_JSON or not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    raise RuntimeError("Missing environment variables")

# ------------------------
# FIREBASE (AUTH ONLY)
# ------------------------
cred = credentials.Certificate(json.loads(FIREBASE_ADMIN_JSON))
firebase_admin.initialize_app(cred)

# ------------------------
# SUPABASE
# ------------------------
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# ------------------------
# CONSTANTS
# ------------------------
ALLOWED_SECTIONS = {
    "models",
    "valuations",
    "research",
    "presentations",
    "dashboard"
}

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-powerpoint",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}

MAX_FILE_SIZE_MB = 20

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
# PUBLIC SECTIONS
# ------------------------
@app.get("/sections")
def get_sections():
    return (
        supabase
        .table("sections")
        .select("*")
        .eq("enabled", True)
        .order("order_no")
        .execute()
        .data
    )


# ------------------------
# PUBLIC DASHBOARD
# ------------------------
@app.get("/dashboard")
def get_dashboard():
    result = (
        supabase
        .table("dashboard")
        .select("*")
        .eq("id", 1)
        .single()
        .execute()
    )

    if not result.data:
        raise HTTPException(status_code=404, detail="Dashboard not configured")

    return result.data

# ------------------------
# FILE UPLOAD
# ------------------------

@app.post("/admin/upload")
async def upload_file(
    section: str,
    file: UploadFile = File(...),
    user=Depends(verify_admin)
):
    section = section.lower()

    if section not in ALLOWED_SECTIONS:
        raise HTTPException(status_code=400, detail="Invalid section")

    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=400, detail="Invalid file type")

    contents = await file.read()
    size_mb = len(contents) / (1024 * 1024)

    if size_mb > MAX_FILE_SIZE_MB:
        raise HTTPException(status_code=400, detail="File too large")

    file_id = str(uuid.uuid4())
    path = f"{file_id}-{file.filename}"

    supabase.storage.from_(section).upload(
        path,
        contents,
        {"content-type": file.content_type}
    )

    public_url = supabase.storage.from_(section).get_public_url(path)

    return {
        "file_url": public_url,
        "file_type": file.content_type,
        "file_name": file.filename
    }

# ------------------------
# CREATE ENTRY
# ------------------------
@app.post("/admin/entry")
def create_entry(
    data: dict,
    user=Depends(verify_admin)
):
    if data.get("section_key") not in ALLOWED_SECTIONS:
        raise HTTPException(status_code=400, detail="Invalid section")

    entry = {
        "id": str(uuid.uuid4()),
        "section_key": data["section_key"],
        "title": data.get("title"),
        "industry": data.get("industry"),
        "description": data.get("description"),
        "file_url": data.get("file_url"),
        "file_type": data.get("file_type"),
        "created_at": datetime.datetime.utcnow().isoformat()
    }

    supabase.table("entries").insert(entry).execute()
    return {"status": "created"}

# ------------------------
# PUBLIC READ
# ------------------------
@app.get("/entries/{section}")
def get_entries(section: str):
    section = section.lower()

    if section not in ALLOWED_SECTIONS:
        raise HTTPException(status_code=404, detail="Section not found")

    return (
        supabase
        .table("entries")
        .select("*")
        .eq("section_key", section)
        .order("created_at", desc=True)
        .execute()
        .data
    )
