import os
import json
import sqlite3
import numpy as np
from pathlib import Path
from datetime import datetime
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from openai import OpenAI

app = FastAPI()
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# SQLite setup - use Railway volume path if available, else local
DB_PATH = os.environ.get("DB_PATH", "/data/questions.db")

def get_db():
    """Get database connection and ensure tables exist."""
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL,
            topic TEXT,
            embedding TEXT NOT NULL,
            cluster_id INTEGER,
            source_channel TEXT,
            source_user TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS clusters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic TEXT,
            count INTEGER DEFAULT 1,
            faq_drafted INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    return conn


    def get_embedding(text: str) -> list[float]:
        """Generate embedding via OpenAI API."""
        response = client.embeddings.create(
            input=text,
            model="text-embedding-3-small"
        )
        return response.data[0].embedding
    
