"""
Memory Store - SQLite-based persistent memory with semantic search.

Stores conversation history and retrieves relevant past interactions
using sentence embeddings for semantic similarity.
"""

import sqlite3
import json
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger("salieri.memory")

try:
    from sentence_transformers import SentenceTransformer
    HAS_TRANSFORMERS = True
except ImportError:
    HAS_TRANSFORMERS = False
    logger.warning("sentence-transformers not installed, semantic search disabled")
    logger.debug("sentence_transformers import failed", exc_info=True)


class MemoryStore:
    """Persistent memory with conversation storage and semantic retrieval."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._init_db()

        self.embedder = None
        self._embedder_loaded = False

    def _ensure_embedder(self):
        """Lazy-load the embedding model (only when needed for semantic search)."""
        if self._embedder_loaded:
            return
        self._embedder_loaded = True

        if HAS_TRANSFORMERS:
            try:
                self.embedder = SentenceTransformer("all-MiniLM-L6-v2")
                logger.info("Memory: Embedding model loaded")
            except Exception as e:
                logger.warning(f"Failed to load embedding model: {e}")

    def _init_db(self):
        """Create database tables if they don't exist."""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_message TEXT NOT NULL,
                salieri_response TEXT NOT NULL,
                emotion TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                category TEXT DEFAULT 'general',
                importance REAL DEFAULT 0.5,
                embedding BLOB,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS user_profile (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)

        self.conn.commit()

    def store_conversation(self, user_msg: str, response: str, emotion: str = "neutral"):
        """Store a conversation exchange."""
        self.conn.execute(
            "INSERT INTO conversations (user_message, salieri_response, emotion) VALUES (?, ?, ?)",
            (user_msg, response, emotion),
        )
        self.conn.commit()

    def store_memory(self, content: str, category: str = "general", importance: float = 0.5):
        """Store a fact or memory with optional embedding."""
        embedding = None
        if self.embedder:
            embedding = self.embedder.encode(content).tobytes()

        self.conn.execute(
            "INSERT INTO memories (content, category, importance, embedding) VALUES (?, ?, ?, ?)",
            (content, category, importance, embedding),
        )
        self.conn.commit()

    def search(self, query: str, limit: int = 5) -> list[dict]:
        """Search for relevant memories and conversations."""
        results = []

        # Always get recent conversations
        recent = self.conn.execute(
            "SELECT user_message, salieri_response, emotion, timestamp "
            "FROM conversations ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        ).fetchall()

        for row in recent:
            results.append({
                "type": "conversation",
                "user": row[0],
                "response": row[1],
                "emotion": row[2],
                "timestamp": row[3],
            })

        # Semantic search if embedder is available
        self._ensure_embedder()
        if self.embedder:
            query_embedding = self.embedder.encode(query)
            all_memories = self.conn.execute(
                "SELECT id, content, category, importance, embedding FROM memories"
            ).fetchall()

            scored = []
            for mem in all_memories:
                if mem[4]:  # Has embedding
                    import numpy as np
                    mem_embedding = np.frombuffer(mem[4], dtype=np.float32)
                    similarity = np.dot(query_embedding, mem_embedding) / (
                        np.linalg.norm(query_embedding) * np.linalg.norm(mem_embedding) + 1e-8
                    )
                    scored.append((similarity, mem))

            scored.sort(key=lambda x: x[0], reverse=True)
            for score, mem in scored[:limit]:
                if score > 0.3:  # Relevance threshold
                    results.append({
                        "type": "memory",
                        "content": mem[1],
                        "category": mem[2],
                        "relevance": float(score),
                    })

        return results

    def get_user_profile(self) -> dict:
        """Get stored user profile data."""
        rows = self.conn.execute("SELECT key, value FROM user_profile").fetchall()
        return {row[0]: row[1] for row in rows}

    def set_user_profile(self, key: str, value: str):
        """Set a user profile value."""
        self.conn.execute(
            "INSERT OR REPLACE INTO user_profile (key, value) VALUES (?, ?)",
            (key, value),
        )
        self.conn.commit()

    def get_recent_context(self, count: int = 10) -> list[dict]:
        """Get recent conversation context for the prompt."""
        rows = self.conn.execute(
            "SELECT user_message, salieri_response FROM conversations "
            "ORDER BY timestamp DESC LIMIT ?",
            (count,),
        ).fetchall()

        context = []
        for row in reversed(rows):
            context.append({"role": "user", "content": row[0]})
            context.append({"role": "assistant", "content": row[1]})
        return context

    def close(self):
        self.conn.close()