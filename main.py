from fastapi import FastAPI, Request, Depends, HTTPException, status
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
import secrets, os, json

app = FastAPI()
templates = Jinja2Templates(directory="templates")
security = HTTPBasic()

# ---------------- CREDENTIALS ----------------
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "finance123"

# ---------------- AUTH FUNCTION ----------------
def admin_auth(credentials: HTTPBasicCredentials = Depends(security)):
    valid_user = secrets.compare_digest(credentials.username, ADMIN_USERNAME)
    valid_pass = secrets.compare_digest(credentials.password, ADMIN_PASSWORD)

    if not (valid_user and valid_pass):
        # ⛔ NO HTML, NO ACCESS
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
            headers={"WWW-Authenticate": "Basic"}
        )

    return True

# ---------------- ROUTES ----------------
@app.get("/")
def public_home(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request}
    )

@app.get("/admin")
def admin_home(
    request: Request,
    _: bool = Depends(admin_auth)  # 🔐 STRICTLY REQUIRED
):
    return templates.TemplateResponse(
        "admin/index.html",
        {"request": request}
    )
