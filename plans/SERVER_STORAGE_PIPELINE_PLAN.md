# Server-Side Document Ingestion & Embedding Pipeline Plan

## Goal
Move document storage and embedding off the local Flask host and onto the Kamiak
cluster's shared storage (`/mnt/na1/eecs/srdesign/vta`), so uploads (button +
Google Drive) are persisted, embedded by the cluster's Ollama
(`nomic-embed-text`), and served via the existing Flask backend over the SSH
tunnel. No Gemini API key required.

## Current State
- Flask backend (`Code/backend/app.py`) runs locally; uploads saved to local
  `uploads/` folder; chunks stored in Supabase via Node backend (`server/`).
- Embeddings now use cluster Ollama (`EMBEDDING_PROVIDER=ollama`).
- Cluster: 500GB shared storage at `/mnt/na1/eecs/srdesign/vta`, Ollama serving
  `vta-assistant` + `nomic-embed-text` on port 11434.

## Architecture

```
[Browser] --upload/GoogleDrive--> [Flask backend (local)] --SSH tunnel--> [Kamiak cluster]
                                                              |
                                                              v
                                                   /mnt/na1/eecs/srdesign/vta
                                                   ├── uploads/        (raw files)
                                                   ├── chunks/         (extracted text + metadata JSON)
                                                   ├── embeddings/     (cached vectors, optional)
                                                   └── models/         (ollama models)
```

## Pipeline Stages

### Stage 1: Ingest (Flask backend, local)
1. User uploads file via `/api/upload` or imports from Google Drive
   (`/api/google-drive/import`).
2. Flask validates file type, generates `file_id`, saves raw file to local
   `uploads/` (temporary buffer).
3. Flask forwards raw file to cluster over SCP/rsync or HTTP push to a
   cluster-side ingest endpoint.

### Stage 2: Persist on Cluster Storage
1. Cluster-side service receives file, writes to
   `/mnt/na1/eecs/srdesign/vta/uploads/<course_id>/<file_id>_<filename>`.
2. File metadata (file_id, course_id, filename, type, upload_time, path) saved
   to a JSON registry or Supabase `course_materials` table.
3. Raw file is the single source of truth; local copy can be deleted after
   successful transfer.

### Stage 3: Extract & Chunk (cluster or Flask)
1. Text extraction based on file type (PDF, DOCX, TXT, audio transcription).
2. Chunk into ~500-token segments with metadata (course_id, file_id, page_number,
   source_type).
3. Store chunks as JSON in `/mnt/na1/eecs/srdesign/vta/chunks/<course_id>/<file_id>.json`
   AND/OR push to Node backend -> Supabase `vector_chunks` table.

### Stage 4: Embed (cluster Ollama)
1. For each chunk, call Ollama `/api/embeddings` (nomic-embed-text) on the
   cluster (localhost:11434, no tunnel needed when running on cluster).
2. Attach embedding vector to chunk metadata.
3. Save embedded chunks to Supabase (via Node backend) or to a local FAISS/
   numpy index on shared storage for fast retrieval.

### Stage 5: Serve (Flask backend, local)
1. Flask receives query with course_id.
2. Flask loads chunks from Supabase (Node backend) or reads from cluster
   storage via SSH/SCP.
3. Embeds query via Ollama tunnel (localhost:11434 -> cluster).
4. Cosine similarity search scoped to course_id.
5. Top-K chunks + question sent to Ollama LLM (vta-assistant) via tunnel.
6. Answer + citations returned to user.

## Key Changes Needed

### A. Cluster-Side Ingest Service
- Create a lightweight FastAPI/Flask service on the cluster (port 9000) that:
  - Accepts file uploads (multipart) + metadata (course_id, file_id).
  - Saves to `/mnt/na1/eecs/srdesign/vta/uploads/`.
  - Triggers extraction + chunking + embedding pipeline.
  - Returns chunk count and status.
- Run under tmux or systemd (no root needed: use `nohup` or tmux).

### B. Flask Backend Changes
- Add `CLUSTER_INGEST_URL` env var (e.g., `http://localhost:9000` via tunnel,
  or direct cluster IP if accessible).
- Modify `upload_file()` to forward files to cluster ingest service instead of
  (or in addition to) local processing.
- Remove local `uploads/` dependency; use cluster paths for serving files.
- Add SSH/SCP helper for file transfer if HTTP push is not desired.

### C. Node Backend Changes
- Update `NODE_API_URL` to point to cluster Node service (or keep local Node
  writing to Supabase).
- Ensure `course_materials` and `vector_chunks` tables store cluster file paths.

### D. Google Drive Integration
- Existing Google Drive import flow downloads files to local temp; forward to
  cluster ingest service.
- Store Google Drive file_id in metadata for re-sync capability.

### E. Embedding on Cluster
- Cluster Ollama already serves `nomic-embed-text`.
- Ingest service calls `localhost:11434/api/embeddings` directly (no tunnel).
- Flask backend calls via tunnel for query-time embedding.

## Storage Layout on Cluster

```
/mnt/na1/eecs/srdesign/vta/
├── uploads/              # Raw uploaded files
│   └── <course_id>/
│       └── <file_id>_<filename>
├── chunks/               # Extracted + chunked text (JSON)
│   └── <course_id>/
│       └── <file_id>.json
├── models/               # Ollama models (already in place)
├── ollama/               # Ollama binary
├── ollama_models/        # Model weights
├── data/                 # Training data
├── hf_cache/             # HuggingFace cache
└── ingest_service/       # Cluster-side FastAPI app
    ├── app.py
    ├── requirements.txt
    └── run.sh
```

## Migration Steps

1. **Phase 1 (Immediate):** Keep current setup (Flask local, Node local,
   embeddings via tunnel). Already working.
2. **Phase 2 (Cluster Ingest):** Deploy cluster-side FastAPI ingest service.
   Forward uploads from Flask to cluster. Store files on shared storage.
3. **Phase 3 (Cluster Node Backend):** Move Node backend to cluster (or keep
   local, pointing to same Supabase). No schema changes.
4. **Phase 4 (Full Cluster):** Run Flask backend on cluster behind gunicorn,
   accessible via tunnel or Tailscale. Local machine becomes thin client.

## Constraints
- Do not modify Supabase schema.
- Keep SimpleAnswerGenerator as fallback.
- Do not commit secrets or .env.
- Preserve course_id scoping in all chunk queries.
- 500GB shared storage — monitor usage, clean up temp files.

## Verification
- Upload a document via button → file appears in cluster storage.
- Google Drive import → file appears in cluster storage.
- Query with course_id → answer cites the uploaded document.
- Out-of-scope question → "not found" (no hallucination).
- Course isolation → Course A cannot retrieve Course B chunks.
