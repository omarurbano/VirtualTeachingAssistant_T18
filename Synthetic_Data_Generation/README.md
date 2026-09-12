# Synthetic Data Generation Pipeline

Generates LoRA/QLoRA-ready training data from Google Drive course files using NVIDIA NIM LLMs.

## Architecture

```
Google Drive Course Files
          │
          ▼
   ┌─────────────┐     ┌──────────────┐     ┌──────────────────┐
   │ drive_loader │────▶│ text_extractor│────▶│  seed_generator  │
   │  (OAuth2)    │     │ (Unstructured)│     │  (NVIDIA NIM)    │
   └─────────────┘     └──────────────┘     └────────┬─────────┘
          │                                          │
     raw bytes                                    Q&A seeds
          │                                          │
          ▼                                          ▼
   ┌──────────────────────────────────────────────────────┐
   │              gen_data.py  (Pipeline Orchestrator)     │
   │  step_augment: seeds → synthetic variants (NIM)      │
   │  step_format_jsonl: output LoRA-ready JSONL          │
   └──────────────────────────┬───────────────────────────┘
                              │
                     training_dataset.jsonl
                              │
                              ▼
                   ┌────────────────────┐
                   │  nemo_finetune/    │
                   │  train_lora.py     │
                   │  (QLoRA via TRL)   │
                   └────────────────────┘

Deployment: scripts/brev_deploy.sh → Brev A100 → scripts/brev_pull.sh
```

## Quick Start

### 1. Install Dependencies

```bash
cd Synthetic_Data_Generation
pip install -r requirements.txt
```

### 2. Set Up Credentials

```bash
# Copy config template
cp config.env.example .env

# Edit .env with your keys:
#   NIM_API_KEY     → get from https://build.nvidia.com/
#   GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET → Google Cloud Console

# Download Google OAuth credentials JSON from Google Cloud Console
# (Drive API enabled, Desktop OAuth client) → save as credentials.json
```

### 3. Run the Pipeline

```bash
# Option A: From Google Drive (needs --folder-id)
python gen_data.py --mode drive --folder-id <GOOGLE_DRIVE_FOLDER_ID>

# Option B: From local course files
python gen_data.py --mode local --input-dir ./data/

# Option C: Augment existing seeds only
python gen_data.py --mode augment --seeds seeds.json --variants 5
```

### 4. Run on NVIDIA Brev Instance (A100 80GB)

```bash
# 1. Configure SSH target (optional, defaults shown):
export BREV_SSH_TARGET="ubuntu@global.prd.ga.run.brev.nvidia.com -p 21425"
export BREV_REMOTE_DIR="~/TradeBuzz-SyntheticData"

# 2. Deploy code to Brev:
bash scripts/brev_deploy.sh

# 3. Run full pipeline (data generation + training):
bash scripts/brev_run.sh drive --folder-id <GOOGLE_DRIVE_FOLDER_ID> --variants 3

# Or run from local files:
bash scripts/brev_run.sh local --variants 3

# 4. Pull results back:
bash scripts/brev_pull.sh
```

**Note:** The Brev instance runs the ENTIRE pipeline (NIM API calls + QLoRA fine-tuning on A100). Your local machine only needs the deploy/run/pull scripts.

### 5. Run LoRA Fine-tuning Only (after dataset generation)

```bash
# On Brev instance:
cd ~/TradeBuzz-SyntheticData/Synthetic_Data_Generation
python nemo_finetune/train_lora.py \
  --dataset output/training_dataset.jsonl \
  --base-model nvidia/nemotron-4-7b-instruct \
  --output-dir ./lora_adapter \
  --epochs 3 \
  --batch-size 4
```

### 6. Dry-Run (verify data without training)

```bash
python nemo_finetune/train_lora.py --dataset output/training_dataset.jsonl --dry-run
```

## Pipeline Modules

| Module | Purpose |
|--------|---------|
| `drive_loader.py` | Google Drive OAuth2 + file listing/downloading |
| `text_extractor.py` | PDF/DOCX/PPTX text extraction via Unstructured |
| `seed_generator.py` | Generate Q&A pairs from course chunks using NVIDIA NIM |
| `nim_client.py` | Unified NVIDIA NIM API client with retries |
| `gen_data.py` | Pipeline orchestrator (CLI entry point) |
| `nemo_finetune/train_lora.py` | QLoRA fine-tuning via HuggingFace TRL |
| `scripts/remote_pipeline.sh` | Brev remote runner (installs deps, runs pipeline + training) |
| `scripts/brev_deploy.sh` | Sync code to Brev instance via rsync/SSH |
| `scripts/brev_run.sh` | Execute pipeline on Brev |
| `scripts/brev_pull.sh` | Pull results from Brev |
| `config.env.example` | Environment variable template |

## Output Format (LoRA-ready JSONL)

```jsonl
{"instruction":"Explain transformers in NLP.","input":"","output":"…","tags":["transformer","attention"],"source_file":"lec1.pdf","cognitive_level":"understand"}
{"instruction":"Quiz me: What is backpropagation?","input":"","output":"…","tags":["gradient","training"],"source_file":"lec2.pdf","cognitive_level":"remember"}
```

## NVIDIA NIM Models

| Model | ID | Use |
|-------|----|-----|
| Llama 3.1 70B | `meta/llama-3.1-70b-instruct` | Seed generation (best quality) |
| Llama 3.1 8B | `meta/llama-3.1-8b-instruct` | Augmentation (fast/cheap) |
| Nemotron 4 7B | `nvidia/nemotron-4-7b-instruct` | Fine-tuning base model |

## Environment Variables

See `config.env.example` for full list. Critical vars:

```bash
export NIM_API_KEY="nvapi-..."        # From build.nvidia.com
export NIM_MODEL="meta/llama-3.1-70b-instruct"
export GOOGLE_CLIENT_ID="..."          # From Google Cloud Console
export GOOGLE_CLIENT_SECRET="..."

# Brev deployment (optional, defaults provided):
export BREV_SSH_TARGET="ubuntu@global.prd.ga.run.brev.nvidia.com -p 21425"
export BREV_REMOTE_DIR="~/TradeBuzz-SyntheticData"
```
