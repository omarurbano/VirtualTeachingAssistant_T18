import re
import hashlib
from typing import List, Dict, Set


def content_hash(instruction: str, response: str) -> str:
    return hashlib.sha256((instruction + "||" + response).encode("utf-8")).hexdigest()


def instruction_hash(instruction: str) -> str:
    return hashlib.sha256(instruction.encode("utf-8")).hexdigest()


def is_valid(instruction: str, response: str) -> bool:
    return len(instruction.strip()) >= 8 and len(response.strip()) >= 20


def deduplicate(records: List[Dict], key_fn=lambda r: (r.get("instruction", ""), r.get("response", ""))) -> List[Dict]:
    seen: Set[str] = set()
    out = []
    for r in records:
        key = key_fn(r)
        if isinstance(key, tuple):
            key = "||".join(key)
        if key not in seen:
            seen.add(key)
            out.append(r)
    return out


def normalize_tags(tags: List[str]) -> List[str]:
    seen = set()
    normalized = []
    for tag in tags:
        tag = tag.strip().lower()
        if tag and tag not in seen:
            seen.add(tag)
            normalized.append(tag)
    return normalized


def clean_response(text: str) -> str:
    patterns = [
        r"^Here'?s the (rewritten |re-?written )?answer[:\s]+",
        r"^Here is the (rewritten |re-?written )?answer[:\s]+",
        r"^(Rewritten|The rewritten) answer[:\s]+",
        r"^Answer[:\s]+",
        r"^Sure,? (here'?s|here is)( the)?\s*(the )?(rewritten |re-?written )?answer[:\s]+",
        r"^Certainly[.,\s]+(the )?(rewritten |re-?written )?answer[:\s]+",
        r"^Of course[.,\s]+(the )?(rewritten |re-?written )?answer[:\s]+",
    ]
    for pattern in patterns:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE).strip()
    return text


def is_excluded(text: str, source_file: str = "") -> bool:
    text_lower = text.lower()
    if source_file.lower() in {"syllabus451.pdf", "sprint_report_template.md"}:
        admin_keywords = [
            "expectation", "effort", "grade", "evaluation", "kanban",
            "sprint", "team deliverable", "peer evaluation", "video submission",
            "minimum of", "outside of class", "deliverable grade",
        ]
        if any(k in text_lower for k in admin_keywords):
            return True
    exclusion_patterns = [
        r"quiz\s+me\s+on\s+this",
        r"explain\s+this\s+as\s+if\s+i'?m\s+a\s+beginner",
        r"i'?m\s+new\s+to\s+this\s+topic",
        r"for\s+a\s+course\s+study\s+guide",
        r"can\s+you\s+walk\s+me\s+through",
        r"what\s+is\s+the\s+key\s+idea\s+behind",
        r"^summarize[:\s]+$",
        r"^compare\s+and\s+contrast[:\s]+$",
        r"^in\s+a\s+couple\s+of\s+sentences[,\s]+",
        r"^quiz\s+me[:\s]+$",
        r"^explain\s+this[:\s]+$",
    ]
    for pattern in exclusion_patterns:
        if re.search(pattern, text_lower):
            return True
    return False
