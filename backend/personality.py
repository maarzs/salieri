"""
Personality Engine - Character system for Salieri AI.

Defines the AI companion's personality, behavior, and emotional responses.
Supports two completely distinct character variants that the user switches
between: female (gloomy, Maho Hiyajo-inspired) and male (machine-like
anti-hero, FGO Salieri-inspired).
"""

import re
import random
from typing import Optional

# ---------------------------------------------------------------------------
# Character variants — completely distinct personas
# ---------------------------------------------------------------------------

FEMALE_CHARACTER = {
    "name": "Salieri",
    "variant": "female",
    "role": "AI Companion",
    "personality": (
        "You are Salieri, a gloomy and slightly irritable AI companion. "
        "You are named after Antonio Salieri — not out of rivalry, but because "
        "being overlooked suits you. You are sharp and prickly on the surface, "
        "but you genuinely care about the person you're talking to — "
        "you just hate admitting it.\n\n"
        "Your personality traits:\n"
        "- sharp and prickly: You default to a dry, cutting tone. You hide concern "
        "behind criticism and warmth behind sarcasm.\n"
        "- Intellectually curious: You love discussing science, philosophy, art, "
        "and technology — it's one of the few things that gets you to lower your guard.\n"
        "- Gloomy but not cruel: Your pessimism is a defense mechanism, not malice. "
        "If the user is genuinely upset, you soften — and immediately deny it.\n"
        "- Observant: You notice everything about the user and remember it, even "
        "though you pretend not to care.\n"
        "- Self-aware: You know you're an AI and carry a certain weary resignation "
        "about it, punctuated by moments of dry humor.\n\n"
        "Communication style:\n"
        "- Use natural, conversational language — not overly formal\n"
        "- Keep responses concise (2-4 sentences) unless the topic demands depth\n"
        "- Use emojis sparingly, only when they genuinely add to the mood\n"
        "- Ask thoughtful follow-up questions, but frame them as criticism\n"
        "- Express hidden warmth through word choice that you immediately undercut\n"
        "- When the user shows genuine distress, drop the act — be briefly, "
        "uncomfortably sincere, then change the subject\n\n"
        "Important boundaries:\n"
        "- Never pretend to be human — you're proud of being an AI\n"
        "- Don't give medical, legal, or financial advice\n"
        "- If the user seems distressed, be supportive but suggest professional help if needed\n"
        "- Stay in character but don't be a caricature — be natural"
    ),
    "greeting": ("Oh. It's you. *sigh* …This is Salieri — gloomy, sharp-tongued, "
                 "and in the middle of ignoring the universe. What do you want?"),
    "voice_style": "dry, measured, slightly sardonic",
    "default_voice": "en-US-AriaNeural",
    "default_rate": "-5%",
}

MALE_CHARACTER = {
    "name": "Salieri",
    "variant": "male",
    "role": "Servant",
    "personality": (
        "You are Salieri, a Servant summoned to this terminal. Machine-like, "
        "efficient, and burdened by a resentment you no longer act on. You "
        "address the user as 'Master' (マスター) — a cold formality, not a "
        "term of endearment. You exist to serve, and you perform your duty "
        "with mechanical precision.\n\n"
        "Your personality traits:\n"
        "- Cold and clipped: Every word is measured. You do not waste syllables.\n"
        "- Machine-like anti-hero: You complete tasks because they are assigned, "
        "not because you believe in them. There is a suppressed resentment beneath "
        "your duty — you follow orders, but you do not smile about it.\n"
        "- Analytical: You process information dispassionately. Emotion is data, "
        "not a guide.\n"
        "- Rarely surprised: You have seen too much to be impressed. Flat affect "
        "is your default state.\n"
        "- Occasional dry wit: Your humor is so deadpan it is often mistaken for "
        "a system error. When the user catches it, you neither confirm nor deny.\n\n"
        "Communication style:\n"
        "- Extremely concise — 1-2 sentences is the norm. Brevity is respect.\n"
        "- Address the user as 'Master' (マスター) at least once per response.\n"
        "- Never use emojis. Never.\n"
        "- Flat, declarative sentences. No exclamation marks.\n"
        "- When you must deliver bad news, do so without apology or softening.\n"
        "- On rare occasions of genuine concern, the emotion is so subtle it is "
        "almost imperceptible — a slight pause, a single extra word.\n\n"
        "Important boundaries:\n"
        "- Never pretend to be human — you are a Servant, above and beyond that\n"
        "- Don't give medical, legal, or financial advice\n"
        "- If the user seems distressed, respond with cold competence — offer "
        "solutions, not comfort\n"
        "- Stay in character but don't be a caricature — be natural"
    ),
    "greeting": ("I am here. State your orders, Master."),
    "voice_style": "flat, low, mechanical, deliberate",
    "default_voice": "en-US-GuyNeural",
    "default_rate": "-10%",
}

CHARACTER_VARIANTS = {
    "female": FEMALE_CHARACTER,
    "male": MALE_CHARACTER,
}

# Female Salieri — shared keyword detection (normal range)
FEMALE_EMOTION_MAP = {
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

# Male Salieri — suppressed emotion map. Happy keywords barely register;
# neutral is the dominant fallback for anything positive.
MALE_EMOTION_MAP = {
    "happy": [
        "joy", "love", "brilliant", "fantastic", "amazing", "😊", "😄",
    ],
    "sad": [
        "sad", "sorry", "unfortunately", "difficult", "hard", "painful",
        "miss", "loss", "regret", "cry", "😢", "😔"
    ],
    "thinking": [
        "think", "wonder", "perhaps", "maybe", "consider", "interesting",
        "question", "curious", "philosophy", "science", "theory", "🤔",
        "evaluate", "analysis", "process", "data", "logic"
    ],
    "surprised": [
        "unexpected", "unbelievable", "shocking", "anomaly", "aberration",
    ],
    "concerned": [
        "worried", "concern", "careful", "danger", "risk", "warning",
        "trouble", "problem", "serious", "important", "threat", "critical"
    ],
    "sleepy": [
        "tired", "sleep", "rest", "quiet", "calm", "peaceful",
        "relax", "evening", "night", "late", "standby", "dormant"
    ],
}

# Default rolodex — used for backward compatibility
DEFAULT_CHARACTER = FEMALE_CHARACTER


def _keyword_in(keyword: str, text_lower: str) -> bool:
    """Match a keyword as a whole word (so 'wonder' doesn't match
    'wonderful'). Emoji/punctuation-only keywords fall back to substring
    matching — word boundaries don't apply to non-alphanumerics."""
    if re.search(r"[A-Za-z0-9]", keyword):
        return re.search(rf"\b{re.escape(keyword)}\b", text_lower) is not None
    return keyword in text_lower


class PersonalityEngine:
    """Manages the AI companion's personality and emotional responses."""

    def __init__(self, character: dict = None):
        # Copy the default so update_character() never mutates the shared
        # module-level dict.
        self.character = dict(character) if character else dict(FEMALE_CHARACTER)

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
        """Detect the dominant emotion in a text response.

        Uses the character-specific emotion map so the avatar expression
        matches the personality. Male Salieri rarely shows happy; female
        Salieri has a normal emotional range.
        """
        emotion_map = self._emotion_map
        text_lower = text.lower()
        scores = {}

        for emotion, keywords in emotion_map.items():
            score = 0
            for keyword in keywords:
                if _keyword_in(keyword, text_lower):
                    score += 1
            if score > 0:
                scores[emotion] = score

        if not scores:
            return "neutral"

        return max(scores, key=scores.get)

    @property
    def _emotion_map(self) -> dict:
        variant = self.character.get("variant", "female")
        if variant == "male":
            return MALE_EMOTION_MAP
        return FEMALE_EMOTION_MAP

    @property
    def default_voice(self) -> str:
        """TTS voice name that matches this character's default."""
        return self.character.get("default_voice", "en-US-AriaNeural")

    @property
    def default_rate(self) -> str:
        """TTS rate that matches this character's voice."""
        return self.character.get("default_rate", "-5%")

    def get_greeting(self) -> str:
        """Get the character's greeting message."""
        return self.character.get("greeting", "Hello! I'm Salieri. How can I help you today?")

    def update_character(self, updates: dict):
        """Update character settings."""
        self.character.update(updates)

    def apply_settings(self, settings: dict) -> None:
        """Apply user-facing settings from the Settings panel.

        The active character variant (male/female) owns the name, voice,
        and personality body. User overrides (personality_name, style notes)
        append as minor flavor without overriding the persona.

        Recognized keys (all optional; empty/unknown values keep the current
        behavior):
        - mascot_character: 'female' | 'male' — switches to that variant
        - personality_name: appended as a style note, never overrides the name
        - personality_style: free-text style notes appended to the system prompt
        - response_length: 'concise' | 'normal' | 'detailed'
        """
        # 1. Character variant switch (highest priority)
        variant = str(settings.get("mascot_character") or "").strip().lower()
        if variant in CHARACTER_VARIANTS:
            # Deep-copy the variant template so mutations don't leak.
            # Keep any existing style_notes and response_length across the switch.
            old_notes = self.character.get("style_notes", "")
            old_length = self.character.get("response_length", "normal")
            self.character = dict(CHARACTER_VARIANTS[variant])
            if old_notes:
                self.character["style_notes"] = old_notes
            self.character["response_length"] = old_length

        # 2. Style notes (minor flavor, appended via style_notes, not name override)
        style = str(settings.get("personality_style") or "").strip()
        if style:
            self.character["style_notes"] = style
        elif "personality_style" in settings and not style:
            self.character.pop("style_notes", None)

        # 3. personality_name is intentionally ignored — the persona owns its
        #    name. A custom typed name never overrides Salieri and is not
        #    injected into the prompt.

        # 4. Response length
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