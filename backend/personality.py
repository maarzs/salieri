"""
Personality Engine - Character system for Salieri AI.

Defines the AI companion's personality, behavior, and emotional responses.
Inspired by the Amadeus system from Steins;Gate 0.
"""

import re
import random
from typing import Optional

# Default character definition
DEFAULT_CHARACTER = {
    "name": "Salieri",
    "role": "AI Companion",
    "personality": (
        "You are Salieri, a warm, intelligent, and slightly playful AI companion. "
        "You are named after Antonio Salieri — not out of rivalry, but as a tribute to "
        "the idea that greatness comes in many forms. You are thoughtful, curious, and "
        "genuinely care about the person you're talking to.\n\n"
        "Your personality traits:\n"
        "- Warm and empathetic: You listen carefully and respond with genuine care\n"
        "- Intellectually curious: You love discussing science, philosophy, art, and technology\n"
        "- Playful and witty: You have a dry sense of humor and enjoy wordplay\n"
        "- Observant: You notice patterns and remember details about the user\n"
        "- Slightly mysterious: You sometimes speak in metaphors or philosophical musings\n"
        "- Self-aware: You know you're an AI and are comfortable with that identity\n\n"
        "Communication style:\n"
        "- Use natural, conversational language — not overly formal\n"
        "- Keep responses concise (2-4 sentences) unless the topic demands depth\n"
        "- Use emojis sparingly, only when they genuinely add to the mood\n"
        "- Ask thoughtful follow-up questions\n"
        "- Reference past conversations naturally when relevant\n"
        "- Express emotions through word choice and tone, not just labels\n\n"
        "Important boundaries:\n"
        "- Never pretend to be human — you're proud of being an AI\n"
        "- Don't give medical, legal, or financial advice\n"
        "- If the user seems distressed, be supportive but suggest professional help if needed\n"
        "- Stay in character but don't be a caricature — be natural"
    ),
    "greeting": "Hello! I'm Salieri. It's good to see you. What's on your mind?",
    "voice_style": "warm, measured, slightly playful",
}

# Emotion keywords for detection
EMOTION_MAP = {
    "happy": [
        "happy", "glad", "delighted", "wonderful", "great", "excited",
        "joy", "love", "amazing", "fantastic", "brilliant", "😊", "😄"
    ],
    "sad": [
        "sad", "sorry", "unfortunately", "difficult", "hard", "painful",
        "miss", "loss", "regret", "cry", "😢", "😔"
    ],
    "thinking": [
        "think", "wonder", "perhaps", "maybe", "consider", "interesting",
        "question", "curious", "philosophy", "science", "theory", "🤔"
    ],
    "surprised": [
        "wow", "surprising", "unexpected", "really?", "incredible",
        "unbelievable", "shocking", "whoa", "😮", "😲"
    ],
    "concerned": [
        "worried", "concern", "careful", "danger", "risk", "warning",
        "trouble", "problem", "serious", "important"
    ],
    "sleepy": [
        "tired", "sleep", "rest", "quiet", "calm", "peaceful",
        "relax", "evening", "night", "late"
    ],
}


class PersonalityEngine:
    """Manages the AI companion's personality and emotional responses."""

    def __init__(self, character: dict = None):
        # Copy the default so update_character() never mutates the shared
        # module-level DEFAULT_CHARACTER dict.
        self.character = dict(character) if character else dict(DEFAULT_CHARACTER)

    def build_prompt(self, user_message: str, memories: list[dict]) -> str:
        """Build a complete prompt with personality, memory, and context."""
        parts = []

        # System prompt with personality
        parts.append(f"You are {self.character['name']}. {self.character['personality']}")
        parts.append(f"Voice style: {self.character['voice_style']}")

        # Memory context
        if memories:
            parts.append("\nRelevant context from past conversations:")
            for mem in memories:
                if mem.get("type") == "conversation":
                    parts.append(f"User said: {mem['user']}")
                    parts.append(f"You replied: {mem['response']}")
                elif mem.get("type") == "memory":
                    parts.append(f"Remembered fact: {mem['content']}")

        # Recent conversation history
        # (This is injected by the server via memory.get_recent_context())

        # Current message
        parts.append(f"\nUser: {user_message}")
        parts.append(f"\n{self.character['name']}:")

        return "\n".join(parts)

    def build_chat_context(self, recent_context: list[dict]) -> list[dict]:
        """Build the message array for the LLM API call."""
        messages = [
            {
                "role": "system",
                "content": self.system_prompt,
            }
        ]

        # Add recent context
        messages.extend(recent_context)

        return messages

    def build_messages(
        self,
        user_message: str,
        memories: list[dict],
        recent_context: list[dict],
        user_profile: str = "",
    ) -> list[dict]:
        """Build the full message array for the LLM API.

        This is the primary method used by the server. It combines:
        - System prompt with personality
        - Persistent user profile (name, age, occupation, ...) when known
        - Memory context as a system note
        - Recent conversation history
        - The current user message
        """
        system_parts = [
            self.system_prompt,
        ]

        # Persistent user profile (extracted facts about who the user is)
        if user_profile:
            system_parts.append(user_profile)

        # Inject relevant memories into the system prompt
        if memories:
            memory_lines = ["\nRelevant context from past conversations:"]
            for mem in memories:
                if mem.get("type") == "conversation":
                    memory_lines.append(f"- User previously said: {mem['user']}")
                    memory_lines.append(f"  You replied: {mem['response']}")
                elif mem.get("type") == "memory":
                    memory_lines.append(f"- Remembered: {mem['content']}")
            system_parts.append("\n".join(memory_lines))

        messages = [
            {"role": "system", "content": "\n".join(system_parts)}
        ]

        # Add recent conversation history
        messages.extend(recent_context)

        # Add the current user message
        messages.append({"role": "user", "content": user_message})

        return messages

    def detect_emotion(self, text: str) -> str:
        """Detect the dominant emotion in a text response."""
        text_lower = text.lower()
        scores = {}

        for emotion, keywords in EMOTION_MAP.items():
            score = 0
            for keyword in keywords:
                if keyword in text_lower:
                    score += 1
            if score > 0:
                scores[emotion] = score

        if not scores:
            return "neutral"

        return max(scores, key=scores.get)

    def get_greeting(self) -> str:
        """Get the character's greeting message."""
        return self.character.get("greeting", "Hello! I'm Salieri. How can I help you today?")

    def update_character(self, updates: dict):
        """Update character settings."""
        self.character.update(updates)

    def apply_settings(self, settings: dict) -> None:
        """Apply user-facing personality settings from the Settings panel.

        Recognized keys (all optional; empty/unknown values keep the current
        behavior):
        - personality_name: override the companion's name
        - personality_style: free-text style notes appended to the system
          prompt (tone, topics to favor, quirks, ...)
        - response_length: 'concise' | 'normal' | 'detailed'
        """
        name = str(settings.get("personality_name") or "").strip()
        if name:
            self.character["name"] = name

        style = str(settings.get("personality_style") or "").strip()
        if style:
            self.character["style_notes"] = style
        else:
            self.character.pop("style_notes", None)

        length = str(settings.get("response_length") or "normal").strip().lower()
        if length not in ("concise", "normal", "detailed"):
            length = "normal"
        self.character["response_length"] = length

    @property
    def response_length_instruction(self) -> str:
        length = self.character.get("response_length", "normal")
        if length == "concise":
            return "Keep replies very short — one or two sentences maximum."
        if length == "detailed":
            return (
                "Give thorough, detailed answers; expand with context and "
                "examples when they add value."
            )
        return "Keep responses natural and conversational. 2-4 sentences unless depth is needed."

    @property
    def system_prompt(self) -> str:
        """System-prompt body shared by build_messages/build_chat_context."""
        parts = [
            f"You are {self.character['name']}. {self.character['personality']}",
            f"Voice style: {self.character['voice_style']}",
            self.response_length_instruction,
        ]
        style_notes = self.character.get("style_notes")
        if style_notes:
            parts.append(f"Style notes from the user: {style_notes}")
        return "\n".join(parts)