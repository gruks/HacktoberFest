"""Ollama REST API client with structured JSON outputs, timeouts, and fallbacks."""
import json
import logging
from typing import Any, Dict, List, Optional, Tuple

import requests
from pantrypal.config import (
    DEFAULT_MODEL,
    LLM_NUM_CTX,
    LLM_TEMPERATURE,
    LLM_TIMEOUT_S,
    OLLAMA_BASE_URL,
)
from pantrypal.models import StepItem

logger = logging.getLogger(__name__)

# JSON schema for Call A: Pick substitute
SUBSTITUTION_SCHEMA = {
    "type": "object",
    "properties": {
        "choice_id": {"type": "string", "description": "Candidate ingredient id chosen"},
        "reason": {"type": "string", "description": "1 sentence justifying taste and macro fit"},
        "taste_note": {"type": "string", "description": "Brief note on flavor impact"},
    },
    "required": ["choice_id", "reason", "taste_note"],
}

# JSON schema for Call B: Rewrite steps
STEP_REWRITE_SCHEMA = {
    "type": "object",
    "properties": {
        "steps": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "minutes": {"type": ["integer", "null"]},
                    "temp_c": {"type": ["integer", "null"]},
                },
                "required": ["text"],
            },
        }
    },
    "required": ["steps"],
}


def is_ollama_available(base_url: str = OLLAMA_BASE_URL) -> bool:
    """Check if the local Ollama daemon is reachable within 1.5 seconds."""
    try:
        r = requests.get(f"{base_url}/api/tags", timeout=1.5)
        return r.status_code == 200
    except Exception:
        return False


def call_ollama_chat(
    messages: List[Dict[str, str]],
    schema: Optional[Dict[str, Any]] = None,
    model: str = DEFAULT_MODEL,
    base_url: str = OLLAMA_BASE_URL,
    timeout: int = LLM_TIMEOUT_S,
) -> Optional[Dict[str, Any]]:
    """
    Call Ollama /api/chat with structured output format and circuit breaker.
    Retries once on malformed response. Returns parsed JSON dict or None.
    """
    url = f"{base_url}/api/chat"
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": LLM_TEMPERATURE,
            "num_ctx": LLM_NUM_CTX,
        },
    }
    if schema:
        payload["format"] = schema

    # Attempt up to 2 times (1 retry)
    for attempt in range(2):
        try:
            resp = requests.post(url, json=payload, timeout=timeout)
            if resp.status_code == 200:
                data = resp.json()
                content = data.get("message", {}).get("content", "").strip()
                if content:
                    try:
                        return json.loads(content)
                    except json.JSONDecodeError:
                        logger.warning(f"Ollama returned non-JSON response on attempt {attempt + 1}")
            else:
                logger.warning(f"Ollama returned status {resp.status_code} on attempt {attempt + 1}")
        except requests.Timeout:
            logger.warning(f"Ollama timed out ({timeout}s) on attempt {attempt + 1}")
            break  # Don't retry if timed out
        except Exception as e:
            logger.warning(f"Ollama request error on attempt {attempt + 1}: {e}")

    return None


def llm_pick_substitute(
    missing_id: str,
    missing_role: str,
    candidates: List[Dict[str, Any]],
    recipe_name: str,
    diet_mode: str,
) -> Optional[Dict[str, str]]:
    """
    Call A: Prompt local LLM to select the single best culinary substitute.
    Strictly constrained to the supplied candidate list.
    """
    if not candidates:
        return None

    candidate_ids = {c["id"] for c in candidates}
    cand_summary = "\n".join(
        [
            f"- ID: '{c['id']}' | Name: {c['name']} | Kcal: {c['kcal']}, P: {c['protein']}g, F: {c['fat']}g"
            for c in candidates
        ]
    )

    prompt = (
        f"You are a professional chef. We are preparing '{recipe_name}' on diet '{diet_mode}'.\n"
        f"The recipe is missing '{missing_id}' which serves the culinary flavor role: '{missing_role}'.\n"
        f"Choose the BEST culinary replacement ONLY from these available candidates:\n"
        f"{cand_summary}\n\n"
        f"Rules:\n"
        f"1. You MUST choose choice_id from the candidate IDs: {list(candidate_ids)}.\n"
        f"2. Provide a 1-sentence reason mentioning taste and macro balance.\n"
        f"3. Provide a brief taste_note."
    )

    messages = [
        {"role": "system", "content": "You are a precise culinary nutritionist. Always output valid JSON matching the schema."},
        {"role": "user", "content": prompt},
    ]

    result = call_ollama_chat(messages, schema=SUBSTITUTION_SCHEMA)
    if result and isinstance(result, dict):
        choice_id = result.get("choice_id", "").strip()
        if choice_id in candidate_ids:
            return {
                "choice_id": choice_id,
                "reason": result.get("reason", "Culinary substitution based on flavor profile."),
                "taste_note": result.get("taste_note", "Preserves flavor balance."),
            }

    # Code fallback heuristic: Pick candidate with closest calorie density
    if candidates:
        first_cand = candidates[0]
        return {
            "choice_id": first_cand["id"],
            "reason": f"Selected {first_cand['name']} as best available role match for {missing_role}.",
            "taste_note": "Direct pantry match.",
        }

    return None


def llm_rewrite_steps(
    original_steps: List[str],
    owned_utensils: List[str],
    method: str,
) -> List[StepItem]:
    """
    Call B: Rewrite recipe steps to use available utensils (e.g. air fryer or microwave).
    Applies range validations: minutes in 1-180, temp_c in 60-260.
    """
    if not is_ollama_available():
        return [StepItem(text=s) for s in original_steps]

    steps_text = "\n".join([f"{i+1}. {s}" for i, s in enumerate(original_steps)])
    prompt = (
        f"Rewrite these cooking steps for a cook with only these utensils: {owned_utensils}.\n"
        f"Original method: {method}.\n"
        f"Original steps:\n{steps_text}\n\n"
        f"Provide practical steps with estimated minutes and temperature in Celsius (temp_c) if baking/air frying."
    )

    messages = [
        {"role": "system", "content": "You are a kitchen assistant. Output valid JSON steps with practical times and temps."},
        {"role": "user", "content": prompt},
    ]

    result = call_ollama_chat(messages, schema=STEP_REWRITE_SCHEMA, timeout=15)
    if result and isinstance(result, dict) and "steps" in result:
        validated_steps = []
        for s in result["steps"]:
            text = s.get("text", "").strip()
            if not text:
                continue
            mins = s.get("minutes")
            temp = s.get("temp_c")

            # Range validation
            if mins is not None and not (1 <= mins <= 180):
                mins = None
            if temp is not None and not (60 <= temp <= 260):
                temp = None

            validated_steps.append(StepItem(text=text, minutes=mins, temp_c=temp))

        if validated_steps:
            return validated_steps

    # Fallback to original steps
    return [StepItem(text=s) for s in original_steps]
