import json
import os
from datetime import UTC, datetime

import aiofiles
import psutil
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.security import OAuth2PasswordRequestForm
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlmodel import Session, select

from auth import (
    create_access_token,
    get_current_admin,
    get_current_manager,
    get_current_user,
    hash_password,
    verify_password,
)
from database.session import create_db_and_tables, get_session
from models.document import Document
from models.user import User, UserCreate, UserResponse
from models.webhook import Webhook
from services.weather import get_weather

load_dotenv()
app = FastAPI(title="SendIt API", version="1.0.0")

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

MAX_FILE_SIZE = int(os.getenv("MAX_UPLOAD_SIZE", str(5 * 1024 * 1024)))

ALLOWED_EXTENSIONS = [".pdf", ".jpg", ".jpeg", ".png", ".docx"]
limiter = Limiter(key_func=get_remote_address)

app.state.limiter = limiter

app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.on_event("startup")
def startup():
    create_db_and_tables()


@app.get("/")
def root():
    return {"message": "Welcome to SendIt Document Management API"}


@app.get("/health")
def health_check():
    """Health check endpoint for monitoring."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
    }


@app.get("/metrics")
def get_metrics(current_user: User = Depends(get_current_admin)):
    """Metrics endpoint for monitoring (admin only)."""
    return {
        "cpu_percent": psutil.cpu_percent(),
        "memory_percent": psutil.virtual_memory().percent,
        "disk_usage": psutil.disk_usage("/").percent,
    }


@app.post("/register", response_model=UserResponse)
def register(user: UserCreate, session: Session = Depends(get_session)):
    existing_user = session.exec(
        select(User).where(User.username == user.username)
    ).first()

    if existing_user:
        raise HTTPException(status_code=400, detail="Username already exists")

    existing_email = session.exec(select(User).where(User.email == user.email)).first()

    if existing_email:
        raise HTTPException(status_code=400, detail="Email already exists")

    db_user = User(
        username=user.username,
        email=user.email,
        hashed_password=hash_password(user.password),
        full_name=user.full_name,
        role=user.role,
    )

    session.add(db_user)
    session.commit()
    session.refresh(db_user)

    return db_user


@app.post("/login")
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: Session = Depends(get_session),
):
    user = session.exec(select(User).where(User.username == form_data.username)).first()

    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    if not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    access_token = create_access_token({"sub": user.username})

    return {"access_token": access_token, "token_type": "bearer"}


def validate_file(file: UploadFile):
    """
    Validate the uploaded file extension.
    Returns (True, "") if valid, otherwise (False, error_message).
    """
    file_extension = os.path.splitext(file.filename)[1].lower()

    if file_extension not in ALLOWED_EXTENSIONS:
        return (
            False,
            f"File type not allowed. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    return True, ""


@app.post("/documents/upload")
@limiter.limit("10/hour")
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    city: str = Form(...),
    description: str | None = Form(None),
    country: str = Form("Kenya"),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """
    Upload a document with validation.
    Enriches the document with weather data.
    """

    # 1. Validate file extension
    file_extension = os.path.splitext(file.filename)[1].lower()

    if file_extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type not allowed. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    # 2. Read and validate file size
    contents = await file.read()
    file_size = len(contents)

    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size is {MAX_FILE_SIZE // (1024 * 1024)} MB",
        )

    # 3. Generate a safe filename
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")

    safe_filename = f"{timestamp}_{current_user.id}_{file.filename.replace(' ', '_')}"

    file_path = os.path.join(UPLOAD_DIR, safe_filename)

    # 4. Save the file
    async with aiofiles.open(file_path, "wb") as out_file:
        await out_file.write(contents)

    # Check if this filename already exists
    existing_documents = session.exec(
        select(Document).where(Document.original_filename == file.filename)
    ).all()

    version = 1

    if existing_documents:
        version = max(doc.version for doc in existing_documents) + 1

    # 5. Create database record
    document = Document(
        filename=safe_filename,
        original_filename=file.filename,
        version=version,
        file_size=file_size,
        file_type=file.content_type or "application/octet-stream",
        city=city,
        country=country,
        description=description,
        uploader_id=current_user.id,
        file_path=file_path,
        status="processing",
    )

    session.add(document)
    session.commit()
    session.refresh(document)

    # 6. Fetch weather information
    try:
        weather_data = await get_weather(city, country)

        if weather_data:
            document.weather_data = json.dumps(weather_data)
            document.weather_fetched_at = datetime.utcnow()
            document.status = "enriched"

            session.add(document)
            session.commit()

    except Exception as e:
        print(f"Weather API error: {e}")

        document.status = "uploaded"

        session.add(document)
        session.commit()

    return {
        "message": "Document uploaded successfully",
        "document_id": document.id,
        "filename": document.original_filename,
        "version": document.version,
        "status": document.status,
    }


@app.get("/documents")
@limiter.limit("30/minute")
def list_documents(
    request: Request,
    status: str | None = None,
    city: str | None = None,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """List all documents with optional filters."""

    query = select(Document)

    # Managers and admins see all documents.
    # Staff see only their own documents.
    if current_user.role not in ["admin", "manager"]:
        query = query.where(Document.uploader_id == current_user.id)

    if status:
        query = query.where(Document.status == status)

    if city:
        query = query.where(Document.city == city)

    return session.exec(query).all()


@app.get("/documents/search")
@limiter.limit("20/minute")
def search_documents(
    request: Request,
    q: str | None = None,
    city: str | None = None,
    status: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """
    Search documents with multiple filters.
    """

    query = select(Document)

    # Staff see only their own documents
    if current_user.role not in ["admin", "manager"]:
        query = query.where(Document.uploader_id == current_user.id)

    if q:
        query = query.where(Document.original_filename.contains(q))

    if city:
        query = query.where(Document.city == city)

    if status:
        query = query.where(Document.status == status)

    if date_from:
        query = query.where(Document.uploaded_at >= date_from)

    if date_to:
        query = query.where(Document.uploaded_at <= date_to)

    return session.exec(query).all()


@app.get("/documents/{document_id}")
@limiter.limit("30/minute")
def get_document(
    request: Request,
    document_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Get a specific document."""

    document = session.get(Document, document_id)

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Staff can only view their own documents
    if (
        current_user.role not in ["admin", "manager"]
        and document.uploader_id != current_user.id
    ):
        raise HTTPException(status_code=403, detail="Access denied")

    return document


@app.delete("/documents/{document_id}")
def delete_document(
    document_id: int,
    current_user: User = Depends(get_current_manager),
    session: Session = Depends(get_session),
):
    """Delete a document (Managers and Admins only)."""

    document = session.get(Document, document_id)

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Delete the physical file
    if os.path.exists(document.file_path):
        os.remove(document.file_path)

    session.delete(document)
    session.commit()

    return {"message": "Document deleted successfully"}


@app.post("/documents/{document_id}/enrich")
@limiter.limit("5/minute")
async def enrich_document(
    request: Request,
    document_id: int,
    current_user: User = Depends(get_current_manager),
    session: Session = Depends(get_session),
):
    """
    Manually trigger weather enrichment for a document.
    """

    document = session.get(Document, document_id)

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    if document.status == "enriched":
        return {"message": "Document already enriched"}

    weather_data = await get_weather(document.city, document.country)

    if weather_data:
        document.weather_data = json.dumps(weather_data)
        document.weather_fetched_at = datetime.utcnow()
        document.status = "enriched"

        session.add(document)
        session.commit()

        return {"message": "Document enriched successfully", "weather": weather_data}

    document.status = "failed"
    session.add(document)
    session.commit()

    raise HTTPException(
        status_code=500, detail="Failed to enrich document with weather data"
    )


@app.get("/documents/{document_id}/weather")
@limiter.limit("10/minute")
def get_document_weather(
    request: Request,
    document_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Get the weather data for a document."""

    document = session.get(Document, document_id)

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    if (
        current_user.role not in ["admin", "manager"]
        and document.uploader_id != current_user.id
    ):
        raise HTTPException(status_code=403, detail="Access denied")

    if not document.weather_data:
        raise HTTPException(
            status_code=404, detail="No weather data available for this document"
        )

    return {
        "document_id": document.id,
        "city": document.city,
        "country": document.country,
        "weather": json.loads(document.weather_data),
    }


@app.post("/webhooks/register")
def register_webhook(
    webhook_url: str,
    event_type: str,
    current_user: User = Depends(get_current_admin),
    session: Session = Depends(get_session),
):
    webhook = Webhook(webhook_url=webhook_url, event_type=event_type)

    session.add(webhook)
    session.commit()
    session.refresh(webhook)

    return {
        "message": "Webhook registered successfully",
        "webhook_id": webhook.id,
        "event_type": webhook.event_type,
    }
