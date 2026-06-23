import os
import json
import datetime
import logging
from typing import Optional, List
from fastapi import FastAPI, HTTPException, status, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.config import settings
from backend.llm_client import LLMClient
from backend.database import get_db, engine, Base
from backend.models import ChatSession, Message

# Create database tables automatically
Base.metadata.create_all(bind=engine)

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

app = FastAPI(
    title="University Student Support Assistant API",
    description="Backend API for retrieving support information augmented with an LLM and Database history.",
    version="2.0.0"
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
    question: str = Field(..., description="The query from the student.")
    session_id: Optional[str] = Field(None, description="The session ID. If not provided, a new session is created.")

class AskResponse(BaseModel):
    session_id: str
    question_id: str
    answer_id: str
    question: str
    answer: str
    category: str
    rag_used: bool
    timestamp: str

class RatingRequest(BaseModel):
    rating: str = Field(..., description="The rating: Good, Average, or Poor.")

class FeedbackRequest(BaseModel):
    question: str = Field(..., description="The student's original query.")
    answer: str = Field(..., description="The assistant's generated response.")
    rating: str = Field(..., description="The rating: Good, Average, or Poor.")

# --- Endpoints ---

@app.get("/health")
async def health_check():
    """
    Checks the system health status, verifying connection to the local LLM.
    """
    llm_ok, llm_msg = await llm_client.check_ollama_health()
    return {
        "status": "healthy" if llm_ok else "degraded",
        "backend": "online",
        "llm_connected": llm_ok,
        "llm_message": llm_msg,
        "model_configured": settings.llm_model,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
    }

@app.get("/sessions", response_model=List[SessionResponse])
def get_sessions(db: Session = Depends(get_db)):
    """Fetch all chat sessions ordered by created_at descending."""
    return db.query(ChatSession).order_by(ChatSession.created_at.desc()).all()

@app.post("/sessions", response_model=SessionResponse)
def create_session(session_data: Optional[SessionCreate] = None, db: Session = Depends(get_db)):
    """Create a new chat session."""
    title = "New Chat"
    if session_data and session_data.title:
        title = session_data.title
    session = ChatSession(title=title)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session

@app.delete("/sessions/{session_id}")
def delete_session(session_id: str, db: Session = Depends(get_db)):
    """Delete a chat session and all associated messages."""
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    db.delete(session)
    db.commit()
    return {"status": "success", "message": "Session deleted successfully"}

@app.get("/sessions/{session_id}/messages", response_model=List[MessageResponse])
def get_session_messages(session_id: str, db: Session = Depends(get_db)):
    """Fetch all messages for a specific session ordered by created_at ascending."""
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return db.query(Message).filter(Message.session_id == session_id).order_by(Message.created_at.asc()).all()

@app.post("/messages/{message_id}/rate")
def rate_message(message_id: str, request: RatingRequest, db: Session = Depends(get_db)):
    """Update feedback rating for a specific assistant message."""
    message = db.query(Message).filter(Message.id == message_id).first()
    if not message:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    if message.role != "assistant":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only assistant responses can be rated")
    if request.rating not in ["Good", "Average", "Poor"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid rating value. Must be Good, Average, or Poor")
    
    message.rating = request.rating
    db.commit()
    return {"status": "success", "message": "Rating saved successfully"}

@app.post("/ask", response_model=AskResponse)
async def ask_question(request: AskRequest, db: Session = Depends(get_db)):
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
        session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    
    if not session:
        # Create a new session if none exists or invalid session_id is provided
        session = ChatSession(title=question[:40] + ("..." if len(question) > 40 else ""))
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

    try:
        # 3. Generate response using LLM & RAG, passing history context
        result = await llm_client.generate_response(question, use_rag=True, history=history)
        
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
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

@app.post("/feedback")
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
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
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
