"""
Memory Store - SQLite-based persistent memory with semantic search.

Stores conversation history and retrieves relevant past interactions
using sentence embeddings for semantic similarity.
"""

import sqlite3
import json
import logging
import re
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


# ---------------------------------------------------------------------------
# Lightweight fact extraction — offline, zero-dependency regex patterns.
# Each entry: (pattern, category, profile_key or None).
# The *last* capture group is always the extracted value (used for profile
# keys); the cleaned full match becomes the stored memory text.
# ---------------------------------------------------------------------------
FACT_PATTERNS = [
    (re.compile(r"\bmy name is\s+([A-Za-z][\w'-]*)", re.I), "name", "name"),
    (re.compile(r"\bi(?:'m| am) called\s+([A-Za-z][\w'-]*)", re.I), "name", "name"),
    (re.compile(r"\bcall me\s+([A-Za-z][\w'-]*)", re.I), "name", "name"),
    (re.compile(r"\bi(?:'m| am)\s+(\d{1,2})\s+years?\s+old\b", re.I), "age", "age"),
    (re.compile(r"\bi (?:work at|work for)\s+(.{2,60}?)(?=[.,!?;]|$)", re.I), "occupation", "occupation"),
    (re.compile(r"\bi live in\s+(.{2,60}?)(?=[.,!?;]|$)", re.I), "location", "location"),
    (re.compile(r"\bmy favorite ([\w ]+?) (?:is|are)\s+(.{2,60}?)(?=[.,!?;]|$)", re.I), "preference", None),
    (re.compile(r"\bi (?:really )?(?:like|love|enjoy)\s+(.{2,60}?)(?=[.,!?;]|$)", re.I), "interest", None),
]

# Guard against verb-clause false positives on the loose like/love pattern,
# e.g. "I like to think that..." must not become an "interest" fact.
_INTEREST_STOP_PREFIXES = (
    "to ", "that ", "when ", "how ", "what ", "where ", "who ", "why ",
    "it when", "being ",
)


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

    def get_history(self, limit: int = 100) -> list[dict]:
        """Return the most recent exchanges, oldest first, for UI restore.

        Timestamps are normalized to epoch milliseconds so the renderer can
        render them directly (SQLite's CURRENT_TIMESTAMP is UTC).
        """
        rows = self.conn.execute(
            "SELECT user_message, salieri_response, emotion, timestamp "
            "FROM conversations ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()

        history = []
        for user_msg, response, emotion, ts in reversed(rows):
            try:
                dt = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
                epoch_ms = int(dt.replace(tzinfo=None).timestamp() * 1000)
            except (TypeError, ValueError):
                epoch_ms = int(datetime.now().timestamp() * 1000)
            history.append({
                "user_message": user_msg,
                "response": response,
                "emotion": emotion or "neutral",
                "timestamp": epoch_ms,
            })
        return history

    def clear_conversations(self) -> int:
        """Delete all stored conversation exchanges. Returns rows removed."""
        cur = self.conn.execute("DELETE FROM conversations")
        self.conn.commit()
        return cur.rowcount or 0

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

    def has_memory(self, content: str, category: str) -> bool:
        """Case-insensitive exact-match dedup check for stored facts."""
        row = self.conn.execute(
            "SELECT 1 FROM memories WHERE lower(content) = lower(?) AND category = ?",
            (content.strip(), category),
        ).fetchone()
        return row is not None

    def extract_facts(self, text: str) -> list[dict]:
        """Scan a user message for personal facts and persist any new ones.

        Zero-dependency (regex only), so it works without the optional
        sentence-transformers install. Returns the newly stored facts so
        callers can log or surface them.
        """
        stored = []
        for pattern, category, profile_key in FACT_PATTERNS:
            for match in pattern.finditer(text):
                value = match.group(match.lastindex).strip()
                if category == "interest" and value.lower().startswith(_INTEREST_STOP_PREFIXES):
                    continue  # verb clause, not a hobby/object of interest
                fact = re.sub(r"\s+", " ", match.group(0)).strip().rstrip(".,!?;")
                if self.has_memory(fact, category):
                    continue
                self.store_memory(fact, category=category)
                if profile_key:
                    self.set_user_profile(profile_key, value)
                stored.append({"content": fact, "category": category})
        if stored:
            logger.info(f"Memory: extracted {len(stored)} fact(s) from user message")
        return stored

    def search(self, query: str, limit: int = 5) -> list[dict]:
        """Return stored FACTS relevant to the query.

        Recent conversations are deliberately NOT included here — the server
        already injects them via get_recent_context(), and returning them
        from both paths duplicated every exchange in the prompt.

        Retrieval strategy:
        - With sentence-transformers installed: cosine similarity over
          stored embeddings (semantic).
        - Without it: keyword-overlap scoring (works offline, zero deps).
        """
        results = []

        all_memories = self.conn.execute(
            "SELECT id, content, category, importance, embedding FROM memories"
        ).fetchall()

        if not all_memories:
            return results

        # Semantic search if embedder is available
        self._ensure_embedder()
        if self.embedder:
            query_embedding = self.embedder.encode(query)
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
            # Facts stored before the embedder was available have no
            # embedding — fall through so keyword scoring can still reach them.
            if results or all(m[4] for m in all_memories):
                return results

        # Keyword fallback: score each fact by overlapping significant words.
        query_words = {
            w for w in re.findall(r"[a-z0-9']+", query.lower())
            if len(w) > 2
        }
        if not query_words:
            return results

        scored = []
        for _id, content, category, importance, _emb in all_memories:
            mem_words = set(re.findall(r"[a-z0-9']+", content.lower()))
            overlap = len(query_words & mem_words)
            if overlap == 0:
                continue
            # Normalized overlap + a small boost for identity-type facts so
            # "what's my name?" reliably surfaces the name fact.
            score = overlap / max(1, min(len(query_words), len(mem_words)))
            if category in ("name", "age", "occupation", "location"):
                score += 0.25 * overlap
            scored.append((score, content, category))

        scored.sort(key=lambda x: x[0], reverse=True)
        for score, content, category in scored[:limit]:
            results.append({
                "type": "memory",
                "content": content,
                "category": category,
                "relevance": round(score, 3),
            })

        return results

    def get_user_profile(self) -> dict:
        """Get stored user profile data."""
        rows = self.conn.execute("SELECT key, value FROM user_profile").fetchall()
        return {row[0]: row[1] for row in rows}

    def profile_summary(self) -> str:
        """Compact one-liner profile block for the system prompt.

        Returns an empty string when nothing is known yet, so callers can
        append it unconditionally.
        """
        profile = self.get_user_profile()
        if not profile:
            return ""
        labels = {
            "name": "Name",
            "age": "Age",
            "occupation": "Occupation",
            "location": "Lives in",
        }
        parts = []
        for key, label in labels.items():
            if profile.get(key):
                parts.append(f"{label}: {profile[key]}")
        return "What you know about the user: " + "; ".join(parts) + "."

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