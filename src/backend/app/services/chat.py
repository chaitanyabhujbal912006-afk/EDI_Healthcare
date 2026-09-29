from __future__ import annotations

import os
import re
from typing import Any
import httpx

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
HF_URL = "https://api-inference.huggingface.co/models/meta-llama/Llama-2-7b-chat-hf"


def _rule_based_fallback(question: str, context: dict[str, Any]) -> str:
    """Generate intelligent offline context response when no external LLM key is configured."""
    q_lower = question.lower()
    tx_type = context.get("transaction_type", context.get("type", "EDI Transaction"))
    errors = context.get("errors", [])
    valid = context.get("valid", len(errors) == 0 if errors else True)
    sender = context.get("sender_id", "N/A")
    receiver = context.get("receiver_id", "N/A")

    if any(k in q_lower for k in ("type", "what is this", "transaction")):
        return f"This transaction is identified as an X12 {tx_type} document."
    
    if any(k in q_lower for k in ("error", "invalid", "issue", "warning", "fail")):
        if not errors:
            return f"The {tx_type} file passed validation with 0 fatal errors. Status: {'Valid' if valid else 'Review required'}."
        err_list = "\n".join(f"- [{e.get('code', 'ERR')}] {e.get('message', '')} at segment {e.get('segment', '')}" for e in errors[:5])
        return f"The file has {len(errors)} validation issues:\n{err_list}"

    if any(k in q_lower for k in ("sender", "receiver", "partner", "parties")):
        return f"Trading Partners:\n- Sender ID: {sender}\n- Receiver ID: {receiver}"

    if any(k in q_lower for k in ("summary", "overview", "describe")):
        return (
            f"Overview of {tx_type}:\n"
            f"- Validation Status: {'Valid' if valid else 'Has Errors'}\n"
            f"- Issues Detected: {len(errors)}\n"
            f"- Sender: {sender} | Receiver: {receiver}\n\n"
            f"Configure GROQ_API_KEY in your .env for deep conversational reasoning."
        )

    return (
        f"EDI Assistant Response for {tx_type}:\n"
        f"Context has {len(errors)} errors recorded. "
        f"To enable natural language Q&A, provide a valid GROQ_API_KEY or HUGGINGFACE_API_KEY in your environment."
    )


async def ask_chat_assistant(question: str, context: dict[str, Any]) -> str:
    """Query Groq (Llama-3.3) -> HuggingFace -> Rule-based fallback."""
    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    hf_token = os.getenv("HUGGINGFACE_API_KEY", "").strip()

    # 1. Try Groq (Llama 3.3) if key is provided
    if groq_key and not groq_key.startswith("your_"):
        prompt = (
            "You are an expert healthcare EDI assistant. Answer concisely and accurately "
            "using only X12 HIPAA 5010 standards and the provided transaction context.\n"
            f"Context: {context}\n"
            f"User Question: {question}"
        )
        headers = {
            "Authorization": f"Bearer {groq_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "llama-3.3-70b-versatile",
            "messages": [
                {"role": "system", "content": "You are a professional healthcare EDI X12 analyst."},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": 450,
            "temperature": 0.2,
        }
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.post(GROQ_URL, json=payload, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    choices = data.get("choices", [])
                    if choices:
                        return choices[0].get("message", {}).get("content", "").strip()
        except Exception:
            pass  # Fall through to next provider

    # 2. Try Hugging Face if configured
    if hf_token:
        prompt = (
            "You are a healthcare EDI assistant. Answer only using X12 HIPAA 5010 context.\n"
            f"Context:\n{context}\n\nQuestion:\n{question}"
        )
        headers = {
            "Authorization": f"Bearer {hf_token}",
            "Content-Type": "application/json",
        }
        payload = {
            "inputs": prompt,
            "parameters": {"max_new_tokens": 450, "temperature": 0.2, "return_full_text": False},
        }
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(HF_URL, json=payload, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    if isinstance(data, list) and data and isinstance(data[0], dict):
                        return str(data[0].get("generated_text", "")).strip()
        except Exception:
            pass

    # 3. Intelligent rule-based fallback
    return _rule_based_fallback(question, context)


# Maintain backward compatibility
ask_huggingface = ask_chat_assistant
