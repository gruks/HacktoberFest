"""Unit tests for llm.py adapter and safety rails."""
from unittest.mock import patch, MagicMock
import pytest
from pantrypal.llm import (
    call_ollama_chat,
    llm_pick_substitute,
    llm_rewrite_steps,
    is_ollama_available,
)


def test_ollama_offline_fallback():
    # When Ollama is offline (requests raises connection error), call_ollama_chat returns None gracefully
    with patch("requests.post", side_effect=Exception("Connection refused")):
        res = call_ollama_chat([{"role": "user", "content": "hello"}], timeout=1)
        assert res is None


def test_llm_pick_substitute_candidate_enforcement():
    candidates = [
        {"id": "vinegar", "name": "White vinegar", "ratio": 0.5, "kcal": 18.0, "protein": 0.0, "fat": 0.0},
        {"id": "lime_juice", "name": "Lime juice", "ratio": 1.0, "kcal": 25.0, "protein": 0.4, "fat": 0.1},
    ]

    # Mock Ollama returning an hallucinated item NOT in candidates
    with patch("pantrypal.llm.call_ollama_chat", return_value={"choice_id": "hallucinated_wine", "reason": "test", "taste_note": "test"}):
        # Should reject hallucination and fall back to top valid candidate
        res = llm_pick_substitute("lemon_juice", "acid", candidates, "Test Recipe", "light_oil_healthy")
        assert res is not None
        assert res["choice_id"] in {"vinegar", "lime_juice"}


def test_llm_rewrite_steps_validation_bounds():
    original_steps = ["Pan fry chicken for 10 minutes at medium heat."]
    # Mock LLM returning step with out-of-bounds temp (e.g. 500 C) and negative minutes
    mock_bad_steps = {
        "steps": [
            {"text": "Bake in hot oven", "minutes": -5, "temp_c": 500}
        ]
    }

    with patch("pantrypal.llm.is_ollama_available", return_value=True), \
         patch("pantrypal.llm.call_ollama_chat", return_value=mock_bad_steps):
        steps = llm_rewrite_steps(original_steps, ["oven"], "bake")
        assert len(steps) == 1
        # Out of bounds minutes & temp_c should be sanitized to None
        assert steps[0].minutes is None
        assert steps[0].temp_c is None
        assert steps[0].text == "Bake in hot oven"
