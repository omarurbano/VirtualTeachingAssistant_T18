# Model Server Integration Plan (VTA)

## 1. Feasibility Verdict

**Achievable, with conditions.**

The existing VTA pipeline already supports:
- Teacher course creation (Node/Express + Supabase)
- Course material upload / Google Drive linking
- Chunking + embedding (Gemini or MiniLM)
- Persistent vector chunks in Supabase (`vector_chunks`)
- Course-scoped retrieval (`course_id` filtering in `retrieve_and_answer`)
- Query tracking to Supabase (`queries` table)

The only missing link is answer generation: `SimpleAnswerGenerator` previously echoed retrieved chunks. It has now been replaced/supplemented with `ModelAnswerGenerator`, which calls the trained model server and falls back to retrieval-only answers when unavailable.

**Not achievable if any of these fail:**
- The trained model cannot be loaded by an inference engine (vLLM/TGI/Ollama) in its current format.
- The model exceeds node VRAM even with quantization (A40 ~48GB, A100 ~80GB).
- WSU HPC policy terminates the persistent inference process.
- The Flask host cannot maintain an SSH tunnel to the GPU node.
- The model server does not expose an HTTP API (OpenAI-compatible preferred).

---

## 2. End-to-End Pipeline (Teacher -> Answer)

### Step A: Teacher creates course
- Frontend -> `POST /course` (Node, port 3000) -> Supabase `courses`.
- Course gets `id`, `code`, `teacher_id`.

### Step B: Teacher links course materials
Two supported paths:
1. Direct upload -> Flask `/api/upload` (course_id in request).
2. Google Drive -> `/api/drive/connect` + sync flow downloads, extracts, chunks, embeds, stores embeddings only.

Each material is recorded in Supabase `course_materials` with `course_id`, `file_name`, `chunks_count`, `file_id`.

### Step C: Embedding pipeline
- `app.py` `process_uploaded_file()` / Drive sync:
  - Extract text/tables/images/audio transcripts.
  - Chunk via `SimpleDocumentProcessor`.
  - Embed via `EmbeddingManager` (Gemini) or `SimpleEmbeddingManager` (MiniLM).
  - Store in in-memory `vector_store` + Supabase `vector_chunks` (with `course_id` metadata).

### Step D: Student query (course-scoped)
- Frontend sends `POST /api/query` with `{ question, course_id }`.
- Flask `query()`:
  - Loads chunks from Supabase if vector store empty.
  - `retrieve_and_answer(question, course_id=...)`:
    - Embed query.
    - Similarity search in `vector_store`.
    - Filter chunks strictly to `course_id`.
    - Re-rank (multimodal scorer).
    - Generate answer via selected generator (model server or fallback).
  - Track query to Supabase `queries` (question, answer, sources, confidence, topics).

### Step E: Answer generation (implemented)
- `ModelAnswerGenerator` builds a grounded prompt from retrieved chunks.
- Calls model server (`MODEL_SERVER_URL/v1/chat/completions`).
- Returns answer text; citations come from retrieval metadata (already built).
- Falls back to `SimpleAnswerGenerator` if server is unreachable or disabled.

---

## 3. HPC Deployment (WSU Kamiak GPU Nodes)

### Given resources
- Users: `omar.urbano-rendon`, `niranjan.sudinani`, `donmanuel.jose`
- Partition: `kamiak`
- GPU hosts: `gpu-2024-a40a/b/c.eecs.wsu.edu`, `gpu-2024-a100a.eecs.wsu.edu`
- Shared storage: `/mnt/na1/eecs/srdesign/vta` (500GB)

### 3.1 Place model weights
```bash
scp -r ./model <NID>@gpu-2024-a40c.eecs.wsu.edu:/mnt/na1/eecs/srdesign/vta/models/
```

### 3.2 Serve model (OpenAI-compatible)
```bash
ssh <NID>@gpu-2024-a40c.eecs.wsu.edu
python -m vllm.entrypoints.openai.api_server \
  --model /mnt/na1/eecs/srdesign/vta/models/<model> \
  --port 8000 \
  --dtype auto \
  --max-model-len 8192
# LoRA variant:
# --enable-lora --lora-modules vta=/path/to/adapter
```

Run under `tmux` so it persists:
```bash
tmux new -s vta-model
# run vLLM command
# Ctrl+B then D to detach
```

### 3.3 Tunnel to Flask host
From the machine running Flask:
```bash
ssh -N -L 8000:localhost:8000 <NID>@gpu-2024-a40c.eecs.wsu.edu
```

### 3.4 Backend configuration (`.env`)
```
USE_MODEL_SERVER=true
MODEL_SERVER_URL=http://localhost:8000
MODEL_SERVER_API_KEY=
MODEL_NAME=<served model id>
MODEL_TIMEOUT_SEC=60
MODEL_MAX_TOKENS=512
MODEL_TEMPERATURE=0.2
```

---

## 4. Code Changes (Implemented)

### 4.1 New file: `Code/backend/model_client.py`
- `health()` -> GET `/v1/models`
- `generate(system_prompt, user_prompt, max_tokens, temperature)` -> POST `/v1/chat/completions`
- Retries with exponential backoff, timeout handling, typed errors.

### 4.2 Modify: `Code/backend/app.py`
- Added `ModelAnswerGenerator` class.
- `RAGApplicationState.initialize()`: selects generator based on `USE_MODEL_SERVER` env flag; falls back on failure.
- Added `/api/model/health` endpoint.
- Hardened course isolation: only chunks with `course_id == requested course_id` are included.

### 4.3 Configuration
- Added model-server variables to `.env` (default `USE_MODEL_SERVER=false`).

---

## 5. Verification Checklist

Before integration:
```bash
# On GPU node
curl -s http://localhost:8000/v1/models

# From Flask host (after tunnel)
curl -s http://localhost:8000/v1/models

# Test completion
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"<name>","messages":[{"role":"user","content":"hi"}]}'
```

After integration:
- [ ] `/api/model/health` returns 200 with `model_server_reachable: true`.
- [ ] Student query returns model-generated answer with citations.
- [ ] Out-of-scope question returns "not found" (no hallucination).
- [ ] Course A student cannot retrieve Course B chunks.
- [ ] Node outage falls back to `SimpleAnswerGenerator`.

---

## 6. Code Removed (No Longer Needed)

The following unused modules were deleted after confirming no runtime imports in `app.py`:

| File | Reason |
|------|--------|
| `Code/backend/enhanced_rag_pipeline.py` | Not imported anywhere; legacy pipeline |
| `Code/backend/answer_generator.py` | Only used by `enhanced_rag_pipeline` |
| `Code/backend/citation_tracker.py` | Only imported by `answer_generator` |
| `Code/backend/gemini_embedding_manager.py` | Not imported in `app.py`; `embedding_manager.py` is used |
| `Code/backend/vectordb.py` | Unused vector DB utilities |
| `Code/backend/multimodal_processor.py` | Only imported by `enhanced_rag_pipeline` |

Additional cleanup recommended (not yet applied):
- Remove debug `print(...)` statements in `/api/query`.
- Keep `SimpleAnswerGenerator` as fallback.

---

## 7. Summary

The pipeline is now wired end-to-end in code. Remaining manual work is HPC-side:
1. Deploy the trained model as an HTTP service on a WSU GPU node.
2. Create the SSH tunnel to the Flask host.
3. Set `USE_MODEL_SERVER=true` and `MODEL_NAME`.

If the model cannot be served over HTTP or the tunnel cannot be maintained, the system safely falls back to retrieval-only answers.
