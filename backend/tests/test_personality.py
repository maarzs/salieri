"""Tests for personality.py — build_messages, system prompt, settings, emotion."""

from personality import DEFAULT_CHARACTER, PersonalityEngine


# ---------------------------------------------------------------------------
# build_messages
# ---------------------------------------------------------------------------

def test_build_messages_structure():
    engine = PersonalityEngine()
    messages = engine.build_messages(
        "How are you?",
        memories=[],
        recent_context=[],
    )
    assert messages[0]["role"] == "system"
    assert messages[-1] == {"role": "user", "content": "How are you?"}
    assert DEFAULT_CHARACTER["name"] in messages[0]["content"]


def test_build_messages_includes_profile_and_memories():
    engine = PersonalityEngine()
    memories = [
        {"type": "memory", "content": "Name: Alice"},
        {"type": "conversation", "user": "I like opera", "response": "Me too"},
    ]
    messages = engine.build_messages(
        "Remember me?",
        memories=memories,
        recent_context=[
            {"role": "user", "content": "earlier question"},
            {"role": "assistant", "content": "earlier answer"},
        ],
        user_profile="What you know about the user: Name: Alice.",
    )
    system = messages[0]["content"]
    assert "Name: Alice" in system
    assert "Remembered: Name: Alice" in system
    assert "User previously said: I like opera" in system
    # Recent context sits between system and the new user message.
    assert messages[1] == {"role": "user", "content": "earlier question"}
    assert messages[2] == {"role": "assistant", "content": "earlier answer"}
    assert messages[-1] == {"role": "user", "content": "Remember me?"}


def test_build_messages_no_memories_no_profile():
    engine = PersonalityEngine()
    messages = engine.build_messages("hi", [], [])
    assert len(messages) == 2
    assert "Relevant context from past conversations" not in messages[0]["content"]


# ---------------------------------------------------------------------------
# apply_settings / system_prompt
# ---------------------------------------------------------------------------

def test_apply_settings_overrides_name_and_style():
    engine = PersonalityEngine()
    engine.apply_settings({
        "personality_name": "Mozart",
        "personality_style": "Be extra dramatic.",
        "response_length": "concise",
    })
    assert engine.character["name"] == "Mozart"
    prompt = engine.system_prompt
    assert prompt.startswith("You are Mozart.")
    assert "Style notes from the user: Be extra dramatic." in prompt
    assert "one or two sentences" in prompt


def test_apply_settings_empty_values_keep_defaults():
    engine = PersonalityEngine()
    engine.apply_settings({"personality_name": "", "personality_style": "   ", "response_length": ""})
    assert engine.character["name"] == "Salieri"
    assert "style_notes" not in engine.character
    assert engine.character["response_length"] == "normal"


def test_apply_settings_invalid_length_falls_back():
    engine = PersonalityEngine()
    engine.apply_settings({"response_length": "essay"})
    assert engine.character["response_length"] == "normal"


def test_response_length_instructions():
    engine = PersonalityEngine()
    engine.apply_settings({"response_length": "detailed"})
    assert "thorough, detailed answers" in engine.response_length_instruction
    engine.apply_settings({"response_length": "concise"})
    assert "very short" in engine.response_length_instruction


def test_update_character_does_not_mutate_shared_default():
    engine = PersonalityEngine()
    engine.update_character({"name": "Changed"})
    fresh = PersonalityEngine()
    assert fresh.character["name"] == "Salieri"
    assert DEFAULT_CHARACTER["name"] == "Salieri"


# ---------------------------------------------------------------------------
# Emotion detection
# ---------------------------------------------------------------------------

def test_detect_emotion_happy():
    assert PersonalityEngine().detect_emotion("That's wonderful, I'm so happy!") == "happy"


def test_detect_emotion_sad():
    assert PersonalityEngine().detect_emotion("I'm sad about the loss, it's painful.") == "sad"


def test_detect_emotion_neutral_fallback():
    assert PersonalityEngine().detect_emotion("The meeting is at noon.") == "neutral"


def test_get_greeting_default():
    greeting = PersonalityEngine().get_greeting()
    assert "Salieri" in greeting
