"""Tests for memory.py — fact extraction, profile, keyword search, history.

The MemoryStore fixture (conftest.py) is forced onto the keyword-search path:
no embedding model is ever loaded, so these tests run fully offline.
"""


# ---------------------------------------------------------------------------
# Fact extraction
# ---------------------------------------------------------------------------

def test_extract_name_fact(memory_store):
    stored = memory_store.extract_facts("Hi! My name is Alice.")
    assert len(stored) == 1
    fact = stored[0]
    assert fact["category"] == "name"
    assert "my name is alice" in fact["content"].lower()
    # Profile must carry the extracted value.
    assert memory_store.get_user_profile()["name"] == "Alice"


def test_extract_multiple_categories(memory_store):
    text = (
        "I'm 34 years old. I live in Vienna. I work at the opera house. "
        "I really enjoy composing symphonies."
    )
    stored = memory_store.extract_facts(text)
    categories = {f["category"] for f in stored}
    assert {"age", "location", "occupation", "interest"} <= categories
    profile = memory_store.get_user_profile()
    assert profile["age"] == "34"
    assert "Vienna" in profile["location"]


def test_extract_dedupes_repeated_facts(memory_store):
    first = memory_store.extract_facts("My name is Bob")
    second = memory_store.extract_facts("Actually, my name is Bob.")
    assert len(first) == 1
    assert second == []  # case-insensitive dedup keeps the store clean


def test_interest_stop_prefixes_rejected(memory_store):
    # Verb-clause false positives must not become "interest" facts.
    assert memory_store.extract_facts("I like to think about music") == []
    assert memory_store.extract_facts("I love that you're here") == []
    assert memory_store.extract_facts("I enjoy being right") == []


def test_no_facts_in_plain_message(memory_store):
    assert memory_store.extract_facts("What do you think about the weather?") == []


# ---------------------------------------------------------------------------
# User profile
# ---------------------------------------------------------------------------

def test_profile_summary_empty_when_unknown(memory_store):
    assert memory_store.profile_summary() == ""


def test_profile_summary_format(memory_store):
    memory_store.set_user_profile("name", "Alice")
    memory_store.set_user_profile("location", "Vienna")
    summary = memory_store.profile_summary()
    assert summary.startswith("What you know about the user: ")
    assert "Name: Alice" in summary
    assert "Lives in: Vienna" in summary
    assert summary.endswith(".")


# ---------------------------------------------------------------------------
# Keyword search (semantic path deliberately disabled in the fixture)
# ---------------------------------------------------------------------------

def test_search_empty_store(memory_store):
    assert memory_store.search("anything") == []


def test_search_surfaces_name_fact(memory_store):
    memory_store.extract_facts("My name is Alice")
    memory_store.store_memory("The user likes opera", category="interest")

    results = memory_store.search("what is my name")
    assert results, "keyword search should find the name fact"
    assert results[0]["category"] == "name"
    assert results[0]["type"] == "memory"
    assert "alice" in results[0]["content"].lower()


def test_search_relevance_ordering(memory_store):
    memory_store.store_memory("The user enjoys composing symphonies", category="interest")
    memory_store.store_memory("The user lives in Vienna", category="location")

    results = memory_store.search("tell me about composing symphonies")
    assert results
    assert "symphonies" in results[0]["content"]


def test_search_respects_limit(memory_store):
    for i in range(8):
        memory_store.store_memory(f"music fact number {i} about composing", category="interest")
    results = memory_store.search("music composing", limit=3)
    assert len(results) == 3


def test_search_no_significant_words(memory_store):
    memory_store.store_memory("The user likes opera", category="interest")
    # Only sub-3-char tokens -> nothing to match on.
    assert memory_store.search("hi ok") == []


# ---------------------------------------------------------------------------
# Conversation history
# ---------------------------------------------------------------------------

def test_history_roundtrip_order_and_shape(memory_store):
    memory_store.store_conversation("first user msg", "first reply", emotion="happy")
    memory_store.store_conversation("second user msg", "second reply")

    history = memory_store.get_history(limit=10)
    assert len(history) == 2
    # Oldest first, UI-ready shape.
    assert history[0]["user_message"] == "first user msg"
    assert history[0]["response"] == "first reply"
    assert history[0]["emotion"] == "happy"
    assert history[1]["emotion"] == "neutral"  # default
    for entry in history:
        assert isinstance(entry["timestamp"], int)
        assert entry["timestamp"] > 0


def test_history_limit_returns_most_recent(memory_store):
    for i in range(5):
        memory_store.store_conversation(f"q{i}", f"a{i}")
    history = memory_store.get_history(limit=2)
    assert [h["user_message"] for h in history] == ["q3", "q4"]


def test_clear_conversations(memory_store):
    memory_store.store_conversation("q", "a")
    removed = memory_store.clear_conversations()
    assert removed == 1
    assert memory_store.get_history() == []
    # Clearing an already-empty store is a no-op.
    assert memory_store.clear_conversations() == 0


def test_recent_context_pairs_user_and_assistant(memory_store):
    memory_store.store_conversation("hello there", "hi!")
    context = memory_store.get_recent_context(count=10)
    assert context == [
        {"role": "user", "content": "hello there"},
        {"role": "assistant", "content": "hi!"},
    ]
