import hashlib
import os
import random
import json
from typing import List, Dict
from dataclasses import dataclass, field

from nim_client import NIMClient


SYSTEM_PROMPT = (
    "You are an expert instructional designer for a university AI course. "
    "Given a passage from course material, generate a diverse set of "
    "student questions and accurate answers. Questions should cover "
    "comprehension, application, analysis, and evaluation levels. "
    "Return only a valid JSON array — no markdown fences, no extra text."
)

OUTPUT_SCHEMA_HINT = """[
  {
    "instruction": "<question text>",
    "response": "<answer text>",
    "cognitive_level": "<remember|understand|apply|analyze|evaluate|create>"
  }
]"""


def content_hash(instruction: str, response: str) -> str:
    return hashlib.sha256((instruction + "||" + response).encode("utf-8")).hexdigest()


def deduplicate(records: List[Dict]) -> List[Dict]:
    seen = set()
    unique = []
    for r in records:
        h = content_hash(r["instruction"], r["response"])
        if h not in seen:
            seen.add(h)
            unique.append(r)
    return unique


def is_valid(record: Dict) -> bool:
    instr = record.get("instruction", "").strip()
    resp = record.get("response", "").strip()
    return len(instr) >= 8 and len(resp) >= 20


def generate_seeds_from_chunks(
    nim: NIMClient,
    chunks: List[str],
    source_file: str,
    num_q_per_chunk: int = 4,
) -> List[Dict]:
    all_seeds: List[Dict] = []
    for i, chunk in enumerate(chunks):
        prompt = (
            f"Source file: {source_file}\n"
            f"Course passage:\n---\n{chunk}\n---\n\n"
            f"Generate {num_q_per_chunk} distinct Q&A pairs from this passage. "
            "Vary question types: definition questions, application questions, "
            "'explain this concept' questions, comparison questions. "
            "Keep answers grounded in the passage and concise (2-5 sentences).\n\n"
            f"Return as JSON matching this schema:\n{OUTPUT_SCHEMA_HINT}"
        )
        try:
            raw = nim.complete(prompt, system_prompt=SYSTEM_PROMPT, temperature=0.6, max_tokens=2048)
            parsed = _safe_parse_json_array(raw)
            for item in parsed:
                item["source_file"] = source_file
                item["chunk_id"] = i
                item["tags"] = _extract_tags(chunk, item)
            all_seeds.extend(parsed)
        except Exception as exc:
            print(f"[seed_gen] chunk {i} failed: {exc}")
            continue
    return deduplicate([r for r in all_seeds if is_valid(r)])


def _safe_parse_json_array(text: str) -> List[Dict]:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        if text.endswith("```"):
            text = text[:-3]
    try:
        data = json.loads(text)
        return data if isinstance(data, list) else [data]
    except json.JSONDecodeError:
        start = text.find("[")
        end = text.rfind("]")
        if start != -1 and end != -1:
            return json.loads(text[start : end + 1])
        return []


def _extract_tags(chunk: str, record: Dict) -> List[str]:
    keywords = [
        "transformer", "attention", "neural network", "gradient", "backprop",
        "embedding", "tokenizer", "fine-tuning", "inference", "training",
        "RAG", "retrieval", "vector", "LoRA", "QLoRA", "quantization",
        "GPU", "CUDA", "tensor", "loss function", "optimizer",
        "NLP", "computer vision", "CNN", "RNN", "LSTM",
        "diffusion", "GAN", "reinforcement learning",
    ]
    chunk_lower = (chunk + " " + record.get("instruction", "")).lower()
    return [kw for kw in keywords if kw.lower() in chunk_lower]
