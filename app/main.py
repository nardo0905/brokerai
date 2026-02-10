import os
from fastapi import FastAPI, Form, HTTPException, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import text
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage
from typing import Optional
from app.agents.scraper import scrape_and_store
from app.voice import transcribe_audio
from app.config import engine, SessionLocal, OLLAMA_URL, LLM_MODEL
from app.models import Appointment

try:
    from app.ml.train_model import train as train_price_model
    from app.ml.predictor import reload_model, is_trained
    _ml_available = True
except ImportError as e:
    print(f"Warning: ML module not available ({e}). /api/ml/* endpoints will return 503.")
    _ml_available = False

# Импортираме нашия оркестратор
try:
    from app.agents.orchestrator import app_orchestrator, workflow
except ImportError as e:
    print(f"Warning: Could not import orchestrator. Error: {e}")
    app_orchestrator = None

app = FastAPI(title="BrokerAI Backend")

# --- Static files (frontend) ---
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# --- Модели за заявките (Pydantic) ---
class ChatRequest(BaseModel):
    message: str
    thread_id: str = "default_user"

# --- Endpoints ---

@app.get("/")
def read_root():
    """Serve the frontend SPA"""
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))

@app.get("/api/status")
def api_status():
    return {"status": "BrokerAI System is Online"}

@app.get("/test-db")
def test_db():
    """Проверява връзка с PostgreSQL"""
    try:
        with engine.connect() as connection:
            result = connection.execute(text("SELECT version();"))
            version = result.fetchone()[0]
        return {"status": "success", "db_version": version}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/test-llm")
def test_llm():
    """Проверява връзка с LLM през Ollama"""
    try:
        llm = ChatOllama(
            base_url=OLLAMA_URL,
            model=LLM_MODEL,
            temperature=0
        )
        response = llm.invoke("Hello!")
        return {"status": "success", "llm_response": response.content}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    """
    Основен endpoint за разговор с BrokerAI.
    """
    if app_orchestrator is None:
        raise HTTPException(status_code=500, detail="Orchestrator not initialized. Check server logs.")

    try:
        # 1. Подготвяме входа за графа
        # HumanMessage идва от langchain_core.messages
        inputs = {
            "messages": [HumanMessage(content=request.message)]
        }
        config = {"configurable": {"thread_id": request.thread_id}}
        
        # 2. Стартираме агента
        result = app_orchestrator.invoke(inputs, config=config)
        
        # 3. Взимаме последния отговор (от AI)
        last_message = result["messages"][-1]
        
        return {
            "response": last_message.content,
            "status": "success"
        }
        
    except Exception as e:
        print(f"Error in chat: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class ScrapeRequest(BaseModel):
    url: Optional[str] = None
    text: Optional[str] = None
    max_pages: int = 3  # За imot.bg пагинация (1-10)

@app.post("/api/scrape")
async def scrape_endpoint(request: ScrapeRequest):
    """
    Активира Scraper Agent-а (SSA).
    Може да приеме URL или суров текст с обяви.
    За imot.bg: поддържа автоматична пагинация (max_pages контролира колко страници).
    """
    if not request.url and not request.text:
        raise HTTPException(status_code=400, detail="Provide either 'url' or 'text'")
    
    result = scrape_and_store(
        url=request.url,
        mock_text=request.text,
        max_pages=min(request.max_pages, 10)  # Хард лимит 10 страници
    )
    return result

# --- Appointments / Scheduler ---

@app.get("/api/appointments")
def list_appointments():
    """Връща всички записани огледи."""
    db = SessionLocal()
    try:
        appointments = db.query(Appointment).order_by(Appointment.created_at.desc()).all()
        return {
            "status": "success",
            "appointments": [
                {
                    "id": a.id,
                    "property_id": a.property_id,
                    "user_contact": a.user_contact,
                    "date_time": a.date_time,
                    "status": a.status,
                    "created_at": str(a.created_at) if a.created_at else None,
                }
                for a in appointments
            ],
        }
    finally:
        db.close()


class AppointmentRequest(BaseModel):
    property_id: int
    date_time: str
    user_contact: str = "Anonymous"


@app.post("/api/appointments")
def create_appointment(request: AppointmentRequest):
    """Създава нов оглед директно (без чат)."""
    db = SessionLocal()
    try:
        new_appt = Appointment(
            property_id=request.property_id,
            user_contact=request.user_contact,
            date_time=request.date_time,
        )
        db.add(new_appt)
        db.commit()
        db.refresh(new_appt)
        return {
            "status": "success",
            "appointment": {
                "id": new_appt.id,
                "property_id": new_appt.property_id,
                "user_contact": new_appt.user_contact,
                "date_time": new_appt.date_time,
                "status": new_appt.status,
            },
        }
    finally:
        db.close()


@app.delete("/api/appointments/{appointment_id}")
def cancel_appointment(appointment_id: int):
    """Отменя (изтрива) оглед."""
    db = SessionLocal()
    try:
        appt = db.query(Appointment).filter(Appointment.id == appointment_id).first()
        if not appt:
            raise HTTPException(status_code=404, detail="Appointment not found")
        db.delete(appt)
        db.commit()
        return {"status": "success", "message": f"Appointment #{appointment_id} cancelled."}
    finally:
        db.close()


# --- ML Model Training ---

@app.post("/api/ml/train")
def train_model_endpoint():
    """Trigger training of the price-prediction model using all scraped properties."""
    if not _ml_available:
        raise HTTPException(status_code=503, detail="ML module not available. Install scikit-learn and rebuild.")
    result = train_price_model()
    if result["status"] == "success":
        reload_model()
    return result


@app.get("/api/ml/status")
def model_status_endpoint():
    """Check whether a trained price model exists."""
    if not _ml_available:
        return {"trained": False, "ml_available": False}
    trained = is_trained()
    return {"trained": trained, "ml_available": True}


@app.post("/api/chat/voice")
async def chat_voice_endpoint(
    file: UploadFile = File(...),
    thread_id: str = Form("default_user"),
):
    """
    Приема аудио файл -> Транскрибира го -> Праща го на Агента -> Връща текст.
    """
    if app_orchestrator is None:
         raise HTTPException(status_code=500, detail="Orchestrator not initialized.")

    # 1. Четем файла
    audio_bytes = await file.read()
    
    # 2. Speech-to-Text
    print("🎤 Receiving audio...")
    user_text = transcribe_audio(audio_bytes, file.filename)
    
    if not user_text:
        return {"status": "error", "message": "Could not understand audio."}
        
    print(f"🗣️ User said: {user_text}")
    
    # 3. Пращаме текста на нашия умен Оркестратор
    try:
        inputs = {"messages": [HumanMessage(content=user_text)]}
        config = {"configurable": {"thread_id": thread_id}}
        result = app_orchestrator.invoke(inputs, config=config)
        last_message = result["messages"][-1]
        
        return {
            "transcription": user_text,
            "response": last_message.content,
            "status": "success"
        }
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))