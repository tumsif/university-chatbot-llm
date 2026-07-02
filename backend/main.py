import os
import json
import datetime
import logging
from typing import Optional, List
from fastapi import FastAPI, HTTPException, status, Depends, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, joinedload

from backend.config import settings
from backend.llm_client import LLMClient
from backend.database import get_db, engine, Base
from backend.models import ChatSession, Message, User, UserDocument
from backend.migrations import run_migrations
from backend.time_utils import now_local_iso, format_local
from backend.auth import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)

# Apply schema migrations (creates tables + patches legacy columns)
run_migrations()

# Ensure logs directory exists
os.makedirs(os.path.dirname(settings.log_file), exist_ok=True)

# Central Logging Configuration
logger = logging.getLogger("backend_logger")
logger.setLevel(logging.INFO)
file_handler = logging.FileHandler(settings.log_file, encoding="utf-8")
formatter = logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s")
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# Add stdout handler for debugging
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

OPENAPI_TAGS = [
    {
        "name": "Health",
        "description": "System and LLM connectivity checks.",
    },
    {
        "name": "Auth",
        "description": "User registration, login, and profile.",
    },
    {
        "name": "Chat",
        "description": "Ask questions — RAG + local LLM pipeline.",
    },
    {
        "name": "Sessions",
        "description": "Chat session history stored in SQLite.",
    },
    {
        "name": "Documents",
        "description": "Upload .txt/.md files for document-based Q&A.",
    },
    {
        "name": "Feedback",
        "description": "Response ratings and legacy feedback logging.",
    },
]

app = FastAPI(
    title="UniSupport AI — Student Support Assistant API",
    description=(
        "Self-hosted UDSM student support backend powered by FastAPI, Ollama, and FAQ-based RAG.\n\n"
        "**Interactive docs:** use this page (`/docs`) to try endpoints.\n\n"
        "**Main flow:** `POST /ask` → FAQ retrieval → Ollama LLM → saved to session history."
    ),
    version="2.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    openapi_tags=OPENAPI_TAGS,
    contact={
        "name": "UniSupport AI",
        "url": "https://unisupport.rejoda.co.tz",
    },
    license_info={
        "name": "Academic project — IS 365",
    },
)

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

llm_client = LLMClient()

# --- Pydantic Schemas ---

class SessionCreate(BaseModel):
    title: Optional[str] = None

class SessionResponse(BaseModel):
    id: str
    title: str
    created_at: datetime.datetime
    document_id: Optional[str] = None
    document_filename: Optional[str] = None

    class Config:
        from_attributes = True


class DocumentResponse(BaseModel):
    id: str
    filename: str
    file_type: str
    char_count: int
    created_at: datetime.datetime

    class Config:
        from_attributes = True

class MessageResponse(BaseModel):
    id: str
    session_id: str
    role: str
    content: str
    category: Optional[str] = None
    rag_used: bool = False
    matched_faq: Optional[str] = None
    rating: Optional[str] = None
    created_at: datetime.datetime

    class Config:
        from_attributes = True

class AskRequest(BaseModel):
    question: str = Field(
        ...,
        description="The student's question in natural language.",
        examples=["How many books can I borrow from the library?"],
    )
    session_id: Optional[str] = Field(
        None,
        description="Existing chat session UUID. Omit to start a new session.",
    )
    document_id: Optional[str] = Field(
        None,
        description="Uploaded document UUID to answer from (.txt / .md).",
    )

    model_config = {"json_schema_extra": {
        "examples": [
            {"question": "When is the ARIS registration deadline?"},
            {"question": "How do I reset my ARIS password?", "session_id": "abc-123"},
        ]
    }}

class AskResponse(BaseModel):
    session_id: str
    question_id: str
    answer_id: str
    question: str
    answer: str
    category: str
    rag_used: bool
    document_used: bool = False
    timestamp: str

    model_config = {"json_schema_extra": {
        "examples": [{
            "session_id": "4fdaa5dd-cf44-4a83-a522-7878d65faf68",
            "question_id": "5bc24767-9f4f-4686-9f11-2d7d10cc5fb2",
            "answer_id": "834af41c-1b03-44e3-be0e-b6c5154281b3",
            "question": "How many books can I borrow?",
            "answer": "Undergraduate students can borrow up to 3 books for 14 days...",
            "category": "Library Services",
            "rag_used": True,
            "timestamp": "2026-06-29 23:22:00",
        }]
    }}

class RatingRequest(BaseModel):
    rating: str = Field(..., description="The rating: Good, Average, or Poor.")

class FeedbackRequest(BaseModel):
    question: str = Field(..., description="The student's original query.")
    answer: str = Field(..., description="The assistant's generated response.")
    rating: str = Field(..., description="The rating: Good, Average, or Poor.")


class UserRegister(BaseModel):
    email: str = Field(..., description="Student email address.")
    password: str = Field(..., min_length=6, description="Account password (min 6 characters).")
    full_name: str = Field(..., min_length=2, description="Full name.")


class UserLogin(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    created_at: datetime.datetime

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


def _get_user_session(db: Session, session_id: str, user: User) -> ChatSession:
    session = (
        db.query(ChatSession)
        .filter(ChatSession.id == session_id, ChatSession.user_id == user.id)
        .first()
    )
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return session


def _get_user_document(db: Session, document_id: str, user: User) -> UserDocument:
    document = (
        db.query(UserDocument)
        .filter(UserDocument.id == document_id, UserDocument.user_id == user.id)
        .first()
    )
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return document


def _session_to_response(session: ChatSession) -> SessionResponse:
    return SessionResponse(
        id=session.id,
        title=session.title,
        created_at=session.created_at,
        document_id=session.document_id,
        document_filename=session.document.filename if session.document else None,
    )


# --- Endpoints ---

@app.get("/", include_in_schema=False)
async def root():
    """Redirect browser root to Swagger UI."""
    return RedirectResponse(url="/docs")


@app.post("/auth/register", response_model=TokenResponse, tags=["Auth"])
def register_user(payload: UserRegister, db: Session = Depends(get_db)):
    """Create a new student account and return an access token."""
    email = payload.email.strip().lower()
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists.",
        )

    user = User(
        email=email,
        full_name=payload.full_name.strip(),
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(user.id)
    logger.info(f"New user registered: {user.email}")
    return TokenResponse(access_token=token, user=user)


@app.post("/auth/login", response_model=TokenResponse, tags=["Auth"])
def login_user(payload: UserLogin, db: Session = Depends(get_db)):
    """Authenticate with email and password."""
    email = payload.email.strip().lower()
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    token = create_access_token(user.id)
    return TokenResponse(access_token=token, user=user)


@app.get("/auth/me", response_model=UserResponse, tags=["Auth"])
def get_me(current_user: User = Depends(get_current_user)):
    """Return the currently authenticated user profile."""
    return current_user


@app.get("/health", tags=["Health"])
async def health_check():
    """
    Checks the system health status, verifying connection to the local LLM.
    """
    llm_ok, llm_msg = await llm_client.check_ollama_health()
    faq_info = llm_client.faq_status()
    return {
        "status": "healthy" if llm_ok and faq_info["faq_entries_loaded"] > 0 else "degraded",
        "backend": "online",
        "llm_connected": llm_ok,
        "llm_message": llm_msg,
        "model_configured": settings.llm_model,
        **faq_info,
        "timestamp": now_local_iso()
    }

@app.get("/sessions", response_model=List[SessionResponse], tags=["Sessions"])
def get_sessions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Fetch all chat sessions for the authenticated user."""
    sessions = (
        db.query(ChatSession)
        .options(joinedload(ChatSession.document))
        .filter(ChatSession.user_id == current_user.id)
        .order_by(ChatSession.created_at.desc())
        .all()
    )
    return [_session_to_response(s) for s in sessions]


@app.post("/sessions", response_model=SessionResponse, tags=["Sessions"])
def create_session(
    session_data: Optional[SessionCreate] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new chat session."""
    title = "New Chat"
    if session_data and session_data.title:
        title = session_data.title
    session = ChatSession(title=title, user_id=current_user.id)
    db.add(session)
    db.commit()
    db.refresh(session)
    return _session_to_response(session)


@app.delete("/sessions/{session_id}", tags=["Sessions"])
def delete_session(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a chat session and all associated messages."""
    session = _get_user_session(db, session_id, current_user)
    db.delete(session)
    db.commit()
    return {"status": "success", "message": "Session deleted successfully"}


@app.get("/sessions/{session_id}/messages", response_model=List[MessageResponse], tags=["Sessions"])
def get_session_messages(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Fetch all messages for a specific session ordered by created_at ascending."""
    _get_user_session(db, session_id, current_user)
    return (
        db.query(Message)
        .filter(Message.session_id == session_id)
        .order_by(Message.created_at.asc())
        .all()
    )


@app.post("/messages/{message_id}/rate", tags=["Feedback"])
def rate_message(
    message_id: str,
    request: RatingRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update feedback rating for a specific assistant message."""
    message = (
        db.query(Message)
        .join(ChatSession, Message.session_id == ChatSession.id)
        .filter(Message.id == message_id, ChatSession.user_id == current_user.id)
        .first()
    )
    if not message:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    if message.role != "assistant":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only assistant responses can be rated")
    if request.rating not in ["Good", "Average", "Poor"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid rating value. Must be Good, Average, or Poor")
    
    message.rating = request.rating
    db.commit()
    return {"status": "success", "message": "Rating saved successfully"}


@app.get("/documents", response_model=List[DocumentResponse], tags=["Documents"])
def list_documents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List uploaded documents for the authenticated user."""
    return (
        db.query(UserDocument)
        .filter(UserDocument.user_id == current_user.id)
        .order_by(UserDocument.created_at.desc())
        .all()
    )


@app.post("/documents/upload", response_model=DocumentResponse, tags=["Documents"])
async def upload_document(
    file: UploadFile = File(...),
    session_id: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload a .txt or .md document for question answering."""
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Filename is required.")

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in settings.allowed_document_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .txt and .md files are supported.",
        )

    raw = await file.read()
    if len(raw) > settings.max_document_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large. Maximum size is {settings.max_document_bytes // 1024} KB.",
        )

    try:
        content = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be valid UTF-8 text.",
        ) from exc

    content = content.strip()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Document is empty.")

    document = UserDocument(
        user_id=current_user.id,
        filename=file.filename,
        content=content,
        file_type=ext.lstrip("."),
        char_count=len(content),
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    if session_id:
        session = (
            db.query(ChatSession)
            .filter(ChatSession.id == session_id, ChatSession.user_id == current_user.id)
            .first()
        )
        if session:
            session.document_id = document.id
            db.commit()

    logger.info(
        f"Document uploaded: '{file.filename}' ({len(content)} chars) by user {current_user.id}"
    )
    return document


@app.delete("/documents/{document_id}", tags=["Documents"])
def delete_document(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete an uploaded document."""
    document = _get_user_document(db, document_id, current_user)
    db.query(ChatSession).filter(
        ChatSession.document_id == document_id,
        ChatSession.user_id == current_user.id,
    ).update({ChatSession.document_id: None})
    db.delete(document)
    db.commit()
    return {"status": "success", "message": "Document deleted successfully"}


@app.post("/ask", response_model=AskResponse, tags=["Chat"])
async def ask_question(
    request: AskRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Accepts student questions, retrieves context (RAG) and chat history,
    queries local LLM, logs details, and saves both messages to the database.
    """
    question = request.question.strip()
    
    # Empty question check
    if not question:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question cannot be empty. Please enter a valid question."
        )

    logger.info(f"Received Question: '{question}' for Session: '{request.session_id}'")

    # 1. Resolve or create chat session
    session_id = request.session_id
    session = None
    if session_id:
        session = (
            db.query(ChatSession)
            .filter(ChatSession.id == session_id, ChatSession.user_id == current_user.id)
            .first()
        )

    if not session:
        # Create a new session if none exists or invalid session_id is provided
        session = ChatSession(
            title=question[:40] + ("..." if len(question) > 40 else ""),
            user_id=current_user.id,
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        session_id = session.id
    else:
        # If session exists and title is default "New Chat", rename it to the first user question
        if session.title == "New Chat":
            session.title = question[:40] + ("..." if len(question) > 40 else "")
            db.commit()

    # 2. Fetch conversation history for this session (limit to last 15 messages for context window)
    history_db = db.query(Message).filter(Message.session_id == session_id).order_by(Message.created_at.asc()).all()
    
    # Format history for LLM client
    history = [{"role": msg.role, "content": msg.content} for msg in history_db]

    document = None
    document_id = request.document_id or (session.document_id if session else None)
    if document_id:
        document = _get_user_document(db, document_id, current_user)
        if session and session.document_id != document.id:
            session.document_id = document.id
            db.commit()

    try:
        # 3. Generate response using LLM & RAG, passing history context
        result = await llm_client.generate_response(
            question,
            use_rag=True,
            history=history,
            document_content=document.content if document else None,
            document_name=document.filename if document else None,
        )
        
        timestamp = format_local()
        
        # 4. Save User Message to database
        import uuid
        user_msg_id = str(uuid.uuid4())
        user_message = Message(
            id=user_msg_id,
            session_id=session_id,
            role="user",
            content=question
        )
        db.add(user_message)

        # 5. Save Assistant Message to database
        assistant_msg_id = str(uuid.uuid4())
        assistant_message = Message(
            id=assistant_msg_id,
            session_id=session_id,
            role="assistant",
            content=result["answer"],
            category=result["category"],
            rag_used=result["rag_used"],
            matched_faq=result["matched_faq"]
        )
        db.add(assistant_message)
        
        db.commit()

        # Log interaction to file
        log_msg = (
            f"Question: '{question}' | "
            f"Answer: '{result['answer']}' | "
            f"Category: {result['category']} | "
            f"RAG: {result['rag_used']} | "
            f"Document: {result.get('document_used', False)} | "
            f"Matched FAQ: {result['matched_faq']}"
        )
        logger.info(f"Successful Interaction: {log_msg}")

        return AskResponse(
            session_id=session_id,
            question_id=user_msg_id,
            answer_id=assistant_msg_id,
            question=question,
            answer=result["answer"],
            category=result["category"],
            rag_used=result["rag_used"],
            document_used=result.get("document_used", False),
            timestamp=timestamp
        )

    except ConnectionError as ce:
        error_msg = f"LLM client connection error: {str(ce)}"
        logger.error(f"Error processing question: '{question}' - {error_msg}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Local LLM is not available. Please ensure Ollama is running. Error details: {str(ce)}"
        )

    except TimeoutError as te:
        error_msg = f"LLM generation timed out: {str(te)}"
        logger.error(f"Error processing question: '{question}' - {error_msg}")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="The local LLM service took too long to generate a response. Please try again."
        )

    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        logger.error(f"Error processing question: '{question}' - {error_msg}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while generating response: {str(e)}"
        )

@app.post("/feedback", tags=["Feedback"])
async def receive_feedback(request: FeedbackRequest):
    """Legacy endpoint supporting feedback file dump."""
    feedback_file = os.path.join(os.path.dirname(settings.log_file), "feedback.json")
    feedback_data = []
    
    if os.path.exists(feedback_file):
        try:
            with open(feedback_file, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    feedback_data = json.loads(content)
        except Exception as e:
            logger.error(f"Error reading feedback file: {str(e)}")
            
    feedback_entry = {
        "timestamp": format_local(),
        "question": request.question,
        "answer": request.answer,
        "rating": request.rating
    }
    feedback_data.append(feedback_entry)
    
    try:
        with open(feedback_file, "w", encoding="utf-8") as f:
            json.dump(feedback_data, f, indent=2)
        logger.info(f"Received user feedback: Question: '{request.question[:30]}...' | Rating: {request.rating}")
        return {"status": "success", "message": "Feedback saved successfully."}
    except Exception as e:
        logger.error(f"Failed to save feedback: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save feedback: {str(e)}"
        )
