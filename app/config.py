import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# --- Database ---
DB_USER = os.getenv("POSTGRES_USER", "broker_admin")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "broker_secret")
DB_NAME = os.getenv("POSTGRES_DB", "broker_ai_db")
DB_HOST = os.getenv("DB_HOST", "db")
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:5432/{DB_NAME}"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# --- LLM ---
OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
LLM_MODEL = os.getenv("LLM_MODEL", "llama3")
