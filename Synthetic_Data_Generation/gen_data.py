#!/usr/bin/env python3
"""
Synthetic Data Generation Pipeline
====================================
Flow: SharePoint → Text Extraction → Seed Generation → Synthetic Augmentation → LoRA JSONL

Usage:
  # Full pipeline from SharePoint:
  python gen_data.py --mode sharepoint --folder-id <SHAREPOINT_FOLDER_ITEM_ID>

  # From Google Drive (legacy):
  python gen_data.py --mode drive --folder-id <GOOGLE_DRIVE_FOLDER_ID>

  # From local files:
  python gen_data.py --mode local --input-dir ./data/

  # From existing seed JSON:
  python gen_data.py --mode seeds --input synthetic_data_*.json

  # Synthetic augmentation only (needs seeds first):
  python gen_data.py --mode augment --seeds seeds.json --output synthetic_dataset.jsonl

Environment variables (from .env):
  NIM_API_KEY       - NVIDIA NIM API key (get from build.nvidia.com)
  NIM_API_BASE      - NIM endpoint (default: https://integrate.api.nvidia.com/v1)
  NIM_MODEL         - Model ID (default: meta/llama-3.1-70b-instruct)
  SHAREPOINT_CLIENT_ID  - Azure AD App Registration client ID
  SHAREPOINT_CLIENT_SECRET - Azure AD client secret
"""

import argparse
import json
import os
import sys
import time
import random
import hashlib
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("synth_pipeline")

# ── Config ──────────────────────────────────────────────────────────────────────
OUTPUT_DIR = "Synthetic_Data_Generation/output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

INSTRUCTION_TEMPLATES = [
    "{instruction}",
    "Explain this as if I'm a beginner: {instruction_lower}",
    "In a couple of sentences, {instruction_lower}",
    "I'm new to this topic — {instruction_lower}",
    "For a course study guide, answer: {instruction_lower}",
    "Quiz me on this: {instruction}",
    "Can you walk me through: {instruction_lower}",
    "What is the key idea behind: {instruction_lower}",
    "Summarize: {instruction_lower}",
    "Compare and contrast: {instruction_lower}",
]

# ── Helpers ─────────────────────────────────────────────────────────────────────

def content_hash(instruction: str, response: str) -> str:
    return hashlib.sha256((instruction + "||" + response).encode("utf-8")).hexdigest()


def is_valid(instruction: str, response: str) -> bool:
    return len(instruction.strip()) >= 8 and len(response.strip()) >= 20


def augment_instruction(instruction: str) -> str:
    tmpl = random.choice(INSTRUCTION_TEMPLATES)
    return tmpl.format(
        instruction=instruction,
        instruction_lower=instruction[0].lower() + instruction[1:],
    )


def deduplicate(records: List[Dict]) -> List[Dict]:
    seen = set()
    out = []
    for r in records:
        h = content_hash(r["instruction"], r["response"])
        if h not in seen:
            seen.add(h)
            out.append(r)
    return out


def write_jsonl(records: List[Dict], filename: str):
    path = os.path.join(OUTPUT_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    log.info("Wrote %d records → %s", len(records), path)


def write_json(records: List[Dict], filename: str):
    path = os.path.join(OUTPUT_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)
    log.info("Wrote %d records → %s", len(records), path)


# ── Pipeline Steps ──────────────────────────────────────────────────────────────

def step_drive(folder_id: str) -> List[Dict]:
    from drive_loader import get_drive_service, list_drive_files, get_file_content
    log.info("Authenticating with Google Drive …")
    service = get_drive_service()
    mime_types = [
        "application/pdf",
        "application/vnd.google-apps.document",
        "application/vnd.google-apps.presentation",
        "text/plain",
        "text/markdown",
    ]
    log.info("Listing files in folder %s …", folder_id)
    files = list_drive_files(service, folder_id=folder_id, mime_types=mime_types)
    log.info("Found %d files.", len(files))
    raw_dir = os.path.join(OUTPUT_DIR, "_raw")
    os.makedirs(raw_dir, exist_ok=True)
    documents: List[Dict] = []
    for f in files:
        log.info("  Downloading: %s (%s)", f["name"], f.get("mimeType", ""))
        try:
            content = get_file_content(service, f["id"], f["mimeType"])
            raw_path = os.path.join(raw_dir, f"{f['id']}_{f['name']}")
            with open(raw_path, "wb") as fh:
                fh.write(content)
            documents.append({"id": f["id"], "name": f["name"], "content": content})
        except Exception as exc:
            log.warning("  Skipped %s: %s", f["name"], exc)
    return documents


def step_extract(documents: List[Dict]) -> List[Dict]:
    from text_extractor import extract_text_from_bytes, chunk_text
    log.info("Extracting and chunking text from %d documents …", len(documents))
    all_chunks: List[Dict] = []
    for doc in documents:
        try:
            text = extract_text_from_bytes(doc["content"], doc["name"])
            chunks = chunk_text(text)
            for i, chunk in enumerate(chunks):
                all_chunks.append({
                    "source_file": doc["name"],
                    "chunk_id": i,
                    "text": chunk,
                })
            log.info("  %s → %d chunks", doc["name"], len(chunks))
        except Exception as exc:
            log.warning("  Extraction failed for %s: %s", doc["name"], exc)
    log.info("Total chunks extracted: %d", len(all_chunks))
    return all_chunks


def step_seed(chunks: List[Dict]) -> List[Dict]:
    from seed_generator import NIMClient, generate_seeds_from_chunks
    log.info("Generating seed Q&A pairs via NVIDIA NIM …")
    nim = NIMClient()
    chunk_texts = [c["text"] for c in chunks]
    source_names = [c["source_file"] for c in chunks]
    unique_sources = list(dict.fromkeys(source_names))
    seeds: List[Dict] = []
    # Process chunks in batches by source file
    for src in unique_sources:
        src_chunks = [c["text"] for c in chunks if c["source_file"] == src]
        log.info("  Processing source: %s (%d chunks)", src, len(src_chunks))
        batch = generate_seeds_from_chunks(nim, src_chunks, src, num_q_per_chunk=4)
        seeds.extend(batch)
        time.sleep(0.5)
    seeds = deduplicate(seeds)
    log.info("Seed Q&A pairs generated: %d", len(seeds))
    write_json(seeds, "seeds.json")
    return seeds


def step_augment(seeds: List[Dict], num_variants: int = 3) -> List[Dict]:
    from nim_client import NIMClient
    log.info("Augmenting %d seeds × %d variants via NVIDIA NIM …", len(seeds), num_variants)
    nim = NIMClient()

    rewrite_prompt = """Rewrite the following answer to match the tone implied by the
new instruction. Keep the content factual, grounded in the original answer, and
safe. Return ONLY the rewritten answer — no preamble, no markdown fences.

New instruction: {instruction}
Original answer: {original_response}"""

    synthetic: List[Dict] = []
    total = len(seeds) * num_variants
    done = 0
    for seed in seeds:
        base_instr = seed["instruction"]
        base_resp = seed["response"]
        tags = seed.get("tags", [])
        for _ in range(num_variants):
            new_instr = augment_instruction(base_instr)
            prompt = rewrite_prompt.format(
                instruction=new_instr, original_response=base_resp
            )
            try:
                new_resp = nim.complete(prompt, temperature=0.7, max_tokens=512)
            except Exception as exc:
                log.warning("  NIM call failed: %s", exc)
                continue
            if not is_valid(new_instr, new_resp):
                continue
            synthetic.append({
                "instruction": new_instr,
                "response": new_resp,
                "tags": tags,
                "source_file": seed.get("source_file", ""),
                "cognitive_level": seed.get("cognitive_level", ""),
            })
            done += 1
            if done % 50 == 0:
                log.info("  Augmented %d/%d …", done, total)
            time.sleep(0.15)

    synthetic = deduplicate(synthetic)
    log.info("Total synthetic records: %d", len(synthetic))
    return synthetic


def step_merge_and_validate(seeds: List[Dict], synthetic: List[Dict]) -> List[Dict]:
    log.info("Merging seeds + synthetic and validating …")
    combined = seeds + synthetic
    combined = deduplicate(combined)
    combined = [r for r in combined if is_valid(r["instruction"], r["response"])]
    log.info("Final dataset size: %d", len(combined))
    return combined


def step_format_jsonl(records: List[Dict], filename: str = "training_dataset.jsonl"):
    import time as _time
    formatted = []
    for r in records:
        formatted.append({
            "instruction": r["instruction"],
            "input": "",
            "output": r["response"],
            "tags": r.get("tags", []),
            "source_file": r.get("source_file", ""),
            "cognitive_level": r.get("cognitive_level", ""),
        })
    write_jsonl(formatted, filename)
    return formatted


# ── Mode runners ────────────────────────────────────────────────────────────────

def step_sharepoint(folder_id: Optional[str] = None) -> List[Dict]:
    from sharepoint_loader import get_sharepoint_service, list_sharepoint_files, get_file_content
    log.info("Authenticating with SharePoint (Microsoft Graph) …")
    service = get_sharepoint_service()
    mime_types = [
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "text/plain",
        "text/markdown",
    ]
    log.info("Listing files from SharePoint drive …")
    files = list_sharepoint_files(service, folder_id=folder_id, mime_types=mime_types)
    log.info("Found %d files.", len(files))
    raw_dir = os.path.join(OUTPUT_DIR, "_raw")
    os.makedirs(raw_dir, exist_ok=True)
    documents: List[Dict] = []
    for f in files:
        log.info("  Downloading: %s (%s)", f["name"], f.get("mimeType", ""))
        try:
            content = get_file_content(service, f["id"], f["mimeType"])
            raw_path = os.path.join(raw_dir, f"{f['id']}_{f['name']}")
            with open(raw_path, "wb") as fh:
                fh.write(content)
            documents.append({"id": f["id"], "name": f["name"], "content": content})
        except Exception as exc:
            log.warning("  Skipped %s: %s", f["name"], exc)
    return documents


def run_sharepoint_mode(folder_id: Optional[str], num_variants: int):
    docs = step_sharepoint(folder_id)
    if not docs:
        log.error("No documents retrieved from SharePoint. Check credentials and permissions.")
        sys.exit(1)
    chunks = step_extract(docs)
    if not chunks:
        log.error("No text chunks extracted.")
        sys.exit(1)
    seeds = step_seed(chunks)
    if not seeds:
        log.error("No seed Q&A pairs generated. Check NIM API key and model.")
        sys.exit(1)
    synthetic = step_augment(seeds, num_variants=num_variants)
    final = step_merge_and_validate(seeds, synthetic)
    step_format_jsonl(final, "training_dataset.jsonl")
    write_json(final, "training_dataset.json")
    log.info("✅ Pipeline complete. Dataset ready in %s", OUTPUT_DIR)


# ── Mode runners ────────────────────────────────────────────────────────────────

def run_drive_mode(folder_id: str, num_variants: int):
    docs = step_drive(folder_id)
    if not docs:
        log.error("No documents retrieved from Drive. Check folder ID and permissions.")
        sys.exit(1)
    chunks = step_extract(docs)
    if not chunks:
        log.error("No text chunks extracted. Documents may be image-only or unsupported formats.")
        sys.exit(1)
    seeds = step_seed(chunks)
    if not seeds:
        log.error("No seed Q&A pairs generated. Check NIM API key and model.")
        sys.exit(1)
    synthetic = step_augment(seeds, num_variants=num_variants)
    final = step_merge_and_validate(seeds, synthetic)
    step_format_jsonl(final, "training_dataset.jsonl")
    write_json(final, "training_dataset.json")
    log.info("✅ Pipeline complete. Dataset ready in %s", OUTPUT_DIR)


def run_local_mode(input_dir: str, num_variants: int):
    from text_extractor import extract_text_from_bytes, chunk_text
    log.info("Scanning local directory: %s", input_dir)
    docs = []
    for fname in os.listdir(input_dir):
        fpath = os.path.join(input_dir, fname)
        if os.path.isfile(fpath):
            with open(fpath, "rb") as f:
                docs.append({"name": fname, "content": f.read()})
    if not docs:
        log.error("No files found in %s", input_dir)
        sys.exit(1)
    chunks = step_extract(docs)
    seeds = step_seed(chunks)
    synthetic = step_augment(seeds, num_variants=num_variants)
    final = step_merge_and_validate(seeds, synthetic)
    step_format_jsonl(final, "training_dataset.jsonl")
    write_json(final, "training_dataset.json")
    log.info("✅ Pipeline complete.")


def run_onedrive_mode(input_dir: Optional[str], num_variants: int):
    from onedrive_loader import find_onedrive_root, default_shared_folder
    root = input_dir or default_shared_folder()
    if not root or not os.path.isdir(root):
        log.error(
            "OneDrive folder not found. Set ONEDRIVE_INPUT_DIR or ensure OneDrive is syncing."
        )
        sys.exit(1)
    log.info("Using OneDrive folder: %s", root)
    run_local_mode(root, num_variants)


def run_seeds_mode(input_path: str, num_variants: int):
    log.info("Loading seed file: %s", input_path)
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        data = data.get("examples", list(data.values()))
    seeds = [r for r in data if isinstance(r, dict) and "instruction" in r and "response" in r]
    log.info("Loaded %d seed records.", len(seeds))
    synthetic = step_augment(seeds, num_variants=num_variants)
    final = step_merge_and_validate(seeds, synthetic)
    step_format_jsonl(final, "training_dataset.jsonl")
    write_json(final, "training_dataset.json")
    log.info("✅ Augmentation complete.")


def run_augment_mode(seeds_path: str, output: str, num_variants: int):
    with open(seeds_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        data = data.get("examples", list(data.values()))
    seeds = [r for r in data if isinstance(r, dict)]
    log.info("Loaded %d seed records from %s", len(seeds), seeds_path)
    synthetic = step_augment(seeds, num_variants=num_variants)
    final = step_merge_and_validate(seeds, synthetic)
    step_format_jsonl(final, output)
    log.info("✅ Augmentation complete.")


# ── CLI ─────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Synthetic Data Generation Pipeline for LoRA/QLoRA Fine-tuning"
    )
    parser.add_argument(
        "--mode",
        choices=["drive", "sharepoint", "onedrive", "local", "seeds", "augment"],
        required=True,
        help="Pipeline mode: drive | sharepoint | onedrive | local | seeds | augment",
    )
    parser.add_argument("--folder-id", help="Google Drive folder ID or SharePoint folder item ID (mode=drive/sharepoint)")
    parser.add_argument("--input-dir", help="Local directory of course files (mode=local/onedrive)")
    parser.add_argument("--input", help="Seed JSON file path (mode=seeds or augment)")
    parser.add_argument("--output", default="training_dataset.jsonl", help="Output filename (mode=augment)")
    parser.add_argument("--variants", type=int, default=3, help="Synthetic variants per seed (default: 3)")
    parser.add_argument("--seeds", help="Seed file path for augment mode")
    args = parser.parse_args()

    if args.mode == "drive":
        if not args.folder_id:
            parser.error("--folder-id is required for mode=drive")
        run_drive_mode(args.folder_id, args.variants)
    elif args.mode == "sharepoint":
        run_sharepoint_mode(args.folder_id, args.variants)
    elif args.mode == "onedrive":
        run_onedrive_mode(args.input_dir, args.variants)
    elif args.mode == "local":
        if not args.input_dir:
            parser.error("--input-dir is required for mode=local")
        run_local_mode(args.input_dir, args.variants)
    elif args.mode == "seeds":
        if not args.input:
            parser.error("--input is required for mode=seeds")
        run_seeds_mode(args.input, args.variants)
    elif args.mode == "augment":
        seeds_path = args.seeds or args.input
        if not seeds_path:
            parser.error("--seeds or --input is required for mode=augment")
        run_augment_mode(seeds_path, args.output, args.variants)


if __name__ == "__main__":
    main()
