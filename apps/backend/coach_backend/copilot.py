"""Copilot answers. Numbers in a spoken reply must already be in the evidence."""

from __future__ import annotations

import json
import math
import re
from typing import Protocol

NUMBER = re.compile(r"(?<![\w.])(-?\d+(?:\.\d+)?)")
TIMESTAMP = re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?")

SYSTEM_PROMPT = """You are a concise racing engineer for the original Assetto Corsa.
Use only the numbers in the supplied context. Never invent telemetry.
If the context is missing or not comparable, say so.
Give one short observation. Do not tell the driver to brake later or carry more speed unless the context marks that recommendation as allowed.
Reply as JSON with keys intent, spoken_response, severity, priority, evidence, trigger_tts.
"""


class LanguageModel(Protocol):
    name: str

    def complete(self, system: str, user: str) -> str: ...


class OllamaModel:
    def __init__(self, host: str, model: str, client) -> None:
        self.name = model
        self.host = host.rstrip("/")
        self._client = client

    def complete(self, system: str, user: str) -> str:
        response = self._client.post(
            f"{self.host}/api/chat",
            json={
                "model": self.name,
                "stream": False,
                "format": "json",
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user},
                ],
            },
            timeout=60,
        )
        response.raise_for_status()
        return str(response.json()["message"]["content"])


def numbers_in(text: str) -> list[float]:
    return [float(match) for match in NUMBER.findall(text)]


def is_grounded(spoken: str, evidence: dict) -> bool:
    allowed = numbers_in(TIMESTAMP.sub(" ", json.dumps(evidence, default=str)))
    for number in numbers_in(spoken):
        if not any(math.isclose(number, candidate, rel_tol=0.02, abs_tol=0.05) for candidate in allowed):
            return False
    return True


def explain(question: str, context: dict) -> dict:
    """Answer from the tool context without a language model."""

    text = question.lower()
    if not context.get("available"):
        return _answer("no_session", "I don't have a recorded session yet.", context)
    delta = context.get("lap_delta") or {}
    best = context.get("best_lap") or {}
    if any(word in text for word in ("delta", "losing", "slower", "time")) and delta.get("available"):
        loss = delta.get("time_loss_s")
        corner = delta.get("corner_name") or "the measured corner"
        return _answer(
            "lap_delta",
            f"The latest lap is {loss} seconds off the reference. The loss in {corner} is {loss} seconds.",
            context,
        )
    if "best" in text and best.get("available"):
        return _answer(
            "best_lap",
            f"The best valid lap is {best.get('lap_time_s')} seconds.",
            context,
        )
    current = context.get("current_lap") or {}
    if current.get("available"):
        return _answer(
            "current_lap",
            f"The current lap number is {current.get('lap_number')} and the lap time is {current.get('lap_time_s')} seconds.",
            context,
        )
    return _answer("insufficient", "I don't have enough comparable laps to answer that.", context)


def _answer(intent: str, spoken: str, evidence: dict) -> dict:
    grounded = is_grounded(spoken, evidence)
    if not grounded:
        spoken = "I don't have enough comparable evidence to answer that."
    return {
        "intent": intent,
        "spoken_response": spoken,
        "severity": "info",
        "priority": 1,
        "evidence": evidence,
        "trigger_tts": False,
        "grounded": True,
        "model": "deterministic-explainer",
    }


def ask(question: str, context: dict, model: LanguageModel | None) -> dict:
    if model is None:
        return explain(question, context)
    raw = model.complete(SYSTEM_PROMPT, json.dumps({"question": question, "context": context}))
    try:
        parsed = json.loads(raw)
        spoken = str(parsed["spoken_response"])
    except (json.JSONDecodeError, KeyError, TypeError):
        fallback = explain(question, context)
        fallback["model"] = "rejected-invalid-output"
        return fallback
    if not is_grounded(spoken, context):
        fallback = explain(question, context)
        fallback["model"] = "rejected-ungrounded"
        return fallback
    return {
        "intent": str(parsed.get("intent") or "answer"),
        "spoken_response": spoken,
        "severity": parsed.get("severity") or "info",
        "priority": int(parsed.get("priority") or 1),
        "evidence": context,
        "trigger_tts": bool(parsed.get("trigger_tts")),
        "grounded": True,
        "model": model.name,
    }


class ScriptedTranscriber:
    def __init__(self, transcript: str) -> None:
        self.transcript = transcript

    def transcribe(self, clip: bytes, sample_rate: int) -> str:
        del clip, sample_rate
        return self.transcript


def answer_audio(clip: bytes, sample_rate: int, question_from_audio, transcriber, synthesizer) -> dict:
    if transcriber is None:
        return {
            "type": "error",
            "code": "stt_unavailable",
            "detail": "No speech-to-text engine is configured. Ask in text, or configure a local engine after benchmarking it.",
        }
    transcript = transcriber.transcribe(clip, sample_rate)
    answer = question_from_audio(transcript)
    if synthesizer is None:
        return {"type": "answer", "transcript": transcript, "answer": answer, "audio_b64": None, "tts": "unavailable"}
    audio = synthesizer.synthesize(answer["spoken_response"])
    import base64

    return {
        "type": "answer",
        "transcript": transcript,
        "answer": answer,
        "audio_b64": base64.b64encode(audio).decode("ascii"),
        "tts": "ready",
    }
