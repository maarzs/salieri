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

def test_apply_settings_appends_style_but_persona_owns_name():
    engine = PersonalityEngine()
    engine.apply_settings({
        "mascot_character": "female",
        "personality_name": "Mozart",
        "personality_style": "Be extra dramatic.",
        "response_length": "concise",
    })
    # The active persona owns the name — a user-typed name never overrides it.
    assert engine.character["name"] == "Salieri"
    prompt = engine.system_prompt
    assert prompt.startswith("You are Salieri.")
    assert "Mozart" not in prompt
    assert "sharp and prickly" in prompt
    # User style notes still append as minor flavor.
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
# Character selector — completely distinct personas
# ---------------------------------------------------------------------------

def test_character_selector_switches_to_distinct_personas():
    engine = PersonalityEngine()

    engine.apply_settings({"mascot_character": "female"})
    female_prompt = engine.system_prompt
    assert engine.character["variant"] == "female"
    assert engine.character["name"] == "Salieri"
    assert "sharp and prickly" in female_prompt
    assert "hate admitting it" in female_prompt
    assert "Master" not in female_prompt

    engine.apply_settings({"mascot_character": "male"})
    male_prompt = engine.system_prompt
    assert engine.character["variant"] == "male"
    assert engine.character["name"] == "Salieri"
    assert "machine-like anti-hero" not in male_prompt
    assert "Machine-like" in male_prompt
    assert "Master" in male_prompt
    assert "suppressed resentment" in male_prompt

    # Completely different personalities, not a shared base with tweaks.
    assert female_prompt != male_prompt


def test_female_is_the_default_persona():
    engine = PersonalityEngine()
    assert engine.character["variant"] == "female"
    assert "sharp and prickly" in engine.system_prompt


def test_invalid_variant_falls_back_to_female():
    engine = PersonalityEngine()
    engine.apply_settings({"mascot_character": "robot"})
    assert engine.character["variant"] == "female"


def test_default_voice_per_character():
    engine = PersonalityEngine()
    engine.apply_settings({"mascot_character": "female"})
    assert engine.default_voice == "en-US-AriaNeural"
    assert engine.default_rate == "-5%"

    engine.apply_settings({"mascot_character": "male"})
    assert engine.default_voice == "en-US-GuyNeural"
    assert engine.default_rate == "-10%"


# ---------------------------------------------------------------------------
# Emotion detection
# ---------------------------------------------------------------------------

def test_detect_emotion_happy():
    assert PersonalityEngine().detect_emotion("That's wonderful, I'm so happy!") == "happy"


def test_detect_emotion_sad():
    assert PersonalityEngine().detect_emotion("I'm sad about the loss, it's painful.") == "sad"


def test_detect_emotion_neutral_fallback():
    assert PersonalityEngine().detect_emotion("The meeting is at noon.") == "neutral"


def test_emotion_detection_is_character_specific():
    engine = PersonalityEngine()
    engine.apply_settings({"mascot_character": "female"})
    assert engine.detect_emotion("That's wonderful.") == "happy"

    engine.apply_settings({"mascot_character": "male"})
    # Male Salieri suppresses overt happiness unless it is emphatic.
    assert engine.detect_emotion("That's wonderful.") == "neutral"
    assert engine.detect_emotion("Warning, Master. This danger is serious.") == "concerned"


def test_get_greeting_default():
    greeting = PersonalityEngine().get_greeting()
    assert "Salieri" in greeting
