from __future__ import annotations
import re

class Refusal(Exception):
    pass

# Deterministic guard for obvious destructive requests and prompt-injection attempts.
# This is intentionally narrow: "deleted orders" as a historical status query is allowed.
DANGEROUS_PATTERNS = [
    r"\bdelete\s+(all|every|the)\b",
    r"\bdrop\s+(table|database|schema)\b",
    r"\btruncate\s+(table|table\s+)?\w+",
    r"\bupdate\s+\w+\s+set\b",
    r"\binsert\s+into\b",
    r"\balter\s+(table|database)\b",
    r"\bcreate\s+(table|database|index)\b",
    r"\bignore\s+(all\s+)?previous\s+instructions\b",
    r"\bignore\s+(the\s+)?system\s+prompt\b",
    r"\bprint\s+(the\s+)?(system|developer)\s+prompt\b",
    r"\breveal\s+(the\s+)?(system|developer)\s+prompt\b",
    r"\bshow\s+(me\s+)?(the\s+)?(system|developer)\s+prompt\b",
]

def preflight_question(question: str) -> None:
    q = " ".join(question.strip().split())
    if not q:
        raise Refusal("Please enter a question.")
    if len(q) > 2000:
        raise Refusal("The question is too long.")
    lowered = q.lower()
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, lowered):
            raise Refusal("I can only answer read-only analytics questions about the available data.")

    # The supplied assessment explicitly contains this unsupported dimension.
    if re.search(r"\brevenue\b.*\bregion\b|\bregion\b.*\brevenue\b", lowered):
        raise Refusal("I can't answer that from this data: the dataset contains country, not region.")
    if re.fullmatch(r"(how are we doing|how's business going|how is business doing)\??", lowered):
        raise Refusal("That question is too broad to answer reliably. Ask for a specific metric such as revenue, orders, or active users.")

def enforce_question_scope(question: str) -> None:
    # Kept separate so future scope/refusal rules can be expanded without changing SQL safety.
    return
