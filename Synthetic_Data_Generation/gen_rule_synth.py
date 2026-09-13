import os
import re
import json
import random
from typing import List, Dict

INPUT_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "data", "cpt_s_course_files"
)
OUTPUT_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "output", "training_dataset_rule.jsonl"
)


def _read_chunks() -> List[Dict]:
    from text_extractor import extract_text_from_bytes, chunk_text

    docs = []
    for fname in os.listdir(INPUT_DIR):
        fpath = os.path.join(INPUT_DIR, fname)
        if not os.path.isfile(fpath):
            continue
        with open(fpath, "rb") as f:
            docs.append({"name": fname, "content": f.read()})

    chunks = []
    for doc in docs:
        try:
            text = extract_text_from_bytes(doc["content"], doc["name"])
            parts = chunk_text(text)
            for i, part in enumerate(parts):
                chunks.append({"source_file": doc["name"], "chunk_id": i, "text": part})
        except Exception:
            continue
    return chunks


def _pick_sentence(text: str) -> str:
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if len(s.strip()) > 20]
    return random.choice(sentences) if sentences else text[:300].strip()


def _make_question(sentence: str) -> str:
    templates = [
        f"Explain this: {sentence}",
        f"What is meant by: {sentence}",
        f"Summarize: {sentence}",
        f"Why does this matter: {sentence}",
        f"How would you explain: {sentence}",
    ]
    return random.choice(templates)


def generate(num_variants: int = 3) -> List[Dict]:
    chunks = _read_chunks()
    records: List[Dict] = []
    seen = set()
    for chunk in chunks:
        text = chunk["text"]
        for _ in range(num_variants):
            answer = _pick_sentence(text)
            question = _make_question(answer)
            key = question + "||" + answer
            if key in seen:
                continue
            seen.add(key)
            records.append(
                {
                    "instruction": question,
                    "input": "",
                    "output": answer,
                    "tags": [],
                    "source_file": chunk["source_file"],
                    "cognitive_level": "understand",
                }
            )
    return records


def main():
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    records = generate(num_variants=3)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"Wrote {len(records)} records -> {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
