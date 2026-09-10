import io
import os
import hashlib
from typing import List, Tuple
import unstructured
from unstructured.partition.auto import partition
from unstructured.documents.elements import (
    NarrativeText, Title, ListItem, Table, Figure, CompositeElement
)

TEXT_MIME_TYPES = {
    "text/plain", "text/markdown", "text/html", "text/csv",
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/rtf",
    "message/rfc822",
}

MIN_CHUNK_CHARS = 120
MAX_CHUNK_CHARS = 1200


def extract_text_from_bytes(content: bytes, filename: str) -> str:
    suffix = os.path.splitext(filename)[1] or ".bin"
    tmp_path = f"_tmp_extract_{hashlib.md5(content).hexdigest()[:8]}{suffix}"
    with open(tmp_path, "wb") as f:
        f.write(content)
    try:
        elements = partition(filename=tmp_path, strategy="fast")
    except Exception:
        try:
            elements = partition(filename=tmp_path, strategy="ocr_only")
        except Exception as exc:
            raise RuntimeError(f"Cannot parse {filename}: {exc}") from exc
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
    return _elements_to_text(elements)


def _elements_to_text(elements) -> str:
    parts: List[str] = []
    for el in elements:
        if isinstance(el, (NarrativeText, Title, ListItem)):
            parts.append(el.text)
        elif isinstance(el, Table):
            rows = [row.cells for row in el.metadata.rows] if el.metadata and el.metadata.rows else []
            if rows:
                parts.append("\n".join(" | ".join(c for c in row) for row in rows))
            else:
                parts.append(el.text or "")
        elif isinstance(el, Figure):
            if el.text:
                parts.append(f"[Image: {el.text}]")
        elif isinstance(el, CompositeElement):
            parts.append(el.text)
        else:
            txt = getattr(el, "text", None)
            if txt:
                parts.append(txt)
    return "\n".join(parts)


def chunk_text(text: str) -> List[str]:
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    chunks: List[str] = []
    buf = ""
    for para in paragraphs:
        if len(buf) + len(para) + 1 > MAX_CHUNK_CHARS and buf:
            chunks.append(buf.strip())
            buf = ""
        buf = f"{buf}\n{para}" if buf else para
    if buf.strip():
        chunks.append(buf.strip())
    merged: List[str] = []
    for chunk in chunks:
        if merged and len(merged[-1]) < MIN_CHUNK_CHARS:
            merged[-1] = f"{merged[-1]}\n{chunk}"
        else:
            merged.append(chunk)
    return merged
