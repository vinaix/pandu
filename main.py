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

if not all([ADMIN_UIDS, FIREBASE_ADMIN_JSON, SUPABASE_URL, SUPABASE_SERVICE_KEY]):
    raise RuntimeError("Missing environment variables")

# ------------------------
# FIREBASE
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
    "dashboard",
    "models",
    "valuations",
    "research",
    "presentations",
    "contact",
}

ALLOWED_MIME_TYPES = {
    # documents
    "application/pdf",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-powerpoint",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    # images
    "image/jpeg",
    "image/png",
    "image/webp",
}

MAX_FILE_SIZE_MB = 20

# ------------------------
# APP
# ------------------------
app = FastAPI(title="CA Portfolio API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://your-domain.com"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------
# AUTH
# ------------------------
def verify_admin(authorization: str = Header(...)):
    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            raise Exception()

        decoded = auth.verify_id_token(token)
        if decoded["uid"] not in ADMIN_UIDS:
            raise Exception()

        return decoded
    except Exception:
        raise HTTPException(status_code=401, detail="Unauthorized")

# ------------------------
# HEALTH
# ------------------------
@app.get("/")
def health():
    return {"status": "running"}

# ------------------------
# PUBLIC
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

@app.get("/dashboard")
def get_dashboard():
    result = (
        supabase
        .table("dashboard")
        .select("*")
        .eq("id", 1)
        .single()
        .execute()
        .data
    )

    if not result:
        raise HTTPException(status_code=404, detail="Dashboard not configured")

    return result

@app.get("/entries/{section}")
def get_entries(section: str):
    if section not in ALLOWED_SECTIONS:
        raise HTTPException(status_code=404)

    return (
        supabase
        .table("entries")
        .select("*")
        .eq("section_key", section)
        .order("created_at", desc=True)
        .execute()
        .data
    )

# ------------------------
# FILE UPLOAD
# ------------------------
@app.post("/admin/upload")
async def upload_file(
    section: str,
    file: UploadFile = File(...),
    user=Depends(verify_admin),
):
    if section not in ALLOWED_SECTIONS:
        raise HTTPException(status_code=400, detail="Invalid section")

    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=400, detail="Invalid file type")

    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large")

    path = f"{uuid.uuid4()}-{file.filename}"

    supabase.storage.from_(section).upload(
        path,
        contents,
        {"content-type": file.content_type},
    )

    public_url = supabase.storage.from_(section).get_public_url(path)

    return {
        "file_url": public_url,
        "file_type": file.content_type,
        "file_name": file.filename,
    }

# ------------------------
# ADMIN – DASHBOARD UPDATE (CRITICAL FIX)
# ------------------------
@app.put("/admin/dashboard")
def update_dashboard(data: dict, user=Depends(verify_admin)):
    existing = (
        supabase
        .table("dashboard")
        .select("*")
        .eq("id", 1)
        .single()
        .execute()
        .data
    )

    if not existing:
        raise HTTPException(status_code=400, detail="Dashboard row missing")

    allowed = {
        "name",
        "title",
        "photo_url",
        "metrics",
        "growth",
        "growth_years",
        "practice_mix",
    }

    payload = {**existing}
    for k in allowed:
        if k in data:
            payload[k] = data[k]

    payload["updated_at"] = datetime.datetime.utcnow().isoformat()

    supabase.table("dashboard").update(payload).eq("id", 1).execute()

    return {"status": "updated"}

# ------------------------
# ADMIN – ENTRY
# ------------------------
@app.post("/admin/entry")
def create_entry(data: dict, user=Depends(verify_admin)):
    supabase.table("entries").insert({
        "id": str(uuid.uuid4()),
        "section_key": data["section_key"],
        "title": data.get("title"),
        "industry": data.get("industry"),
        "description": data.get("description"),
        "file_url": data.get("file_url"),
        "file_type": data.get("file_type"),
        "created_at": datetime.datetime.utcnow().isoformat(),
    }).execute()

    return {"status": "created"}

@app.delete("/admin/entry/{entry_id}")
def delete_entry(entry_id: str, user=Depends(verify_admin)):
    supabase.table("entries").delete().eq("id", entry_id).execute()
    return {"status": "deleted"}
