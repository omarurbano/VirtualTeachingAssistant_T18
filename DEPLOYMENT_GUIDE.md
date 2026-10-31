# Deployment Guide: Render (Backend) + Vercel (Frontend)

## Architecture

```
[Vercel Frontend] --API calls--> [Render Flask Backend] --HTTP--> [Cloudflare Tunnel] --> [Kamiak Cluster]
                                                                                  ├── Ollama (port 11434)
                                                                                  │   ├── vta-assistant (LLM)
                                                                                  │   └── nomic-embed-text (embeddings)
                                                                                  └── Ingest Service (port 9000)
                                                                                      └── /mnt/na1/eecs/srdesign/vta (500GB)
[Render Node Backend] --Supabase--> [Supabase PostgreSQL]
```

## Prerequisites

1. GitHub repository with this project pushed.
2. Render account (free tier works for testing).
3. Vercel account (free tier works).
4. Cloudflare account (for tunnel) OR ngrok account.
5. Supabase project (already configured).

## Step 1: Expose Cluster Services (Cloudflare Tunnel)

The cluster's Ollama and ingest service need public URLs since Render can't SSH tunnel.

On the cluster (gpu-2024-a40c), install cloudflared:
```bash
wget https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64
chmod +x cloudflared-linux-amd64
mv cloudflared-linux-amd64 /mnt/na1/eecs/srdesign/vta/cloudflared
```

Create a tunnel config:
```bash
cat > /mnt/na1/eecs/srdesign/vta/cloudflared-config.yml << 'EOF'
tunnel: <your-tunnel-id>
credentials-file: /mnt/na1/eecs/srdesign/vta/tunnel-creds.json
ingress:
  - hostname: ollama.yourdomain.com
    service: http://localhost:11434
  - hostname: ingest.yourdomain.com
    service: http://localhost:9000
  - service: http_status:404
EOF
```

Run the tunnel under tmux:
```bash
tmux new-session -d -s vta-tunnel "/mnt/na1/eecs/srdesign/vta/cloudflared tunnel --config /mnt/na1/eecs/srdesign/vta/cloudflared-config.yml run"
```

Alternatively, use ngrok:
```bash
# On cluster
ngrok http 11434  # for Ollama
ngrok http 9000    # for ingest (separate terminal)
```

## Step 2: Deploy Backend on Render

1. Push this repo to GitHub.
2. Go to Render Dashboard → New → Web Service.
3. Connect your GitHub repo.
4. Render will auto-detect `render.yaml` and create two services:
   - `vta-flask-backend` (Python)
   - `vta-node-backend` (Node.js)
5. Set environment variables in Render Dashboard:
   - `MODEL_SERVER_URL` = `https://ollama.yourdomain.com` (your tunnel URL)
   - `CLUSTER_INGEST_URL` = `https://ingest.yourdomain.com` (your tunnel URL)
   - `NODE_API_URL` = `https://vta-node-backend.onrender.com`
   - `SUPABASE_URL` = your Supabase URL
   - `SUPABASE_KEY` = your Supabase anon key
6. Deploy. Render will build and start both services.

## Step 3: Deploy Frontend on Vercel

1. Go to Vercel Dashboard → New Project.
2. Import your GitHub repo.
3. Vercel will auto-detect `vercel.json`.
4. Set environment variable:
   - `VTA_BACKEND_URL` = `https://vta-flask-backend.onrender.com`
5. Deploy.

## Step 4: Verify

1. Check Render Flask health: `https://vta-flask-backend.onrender.com/api/model/health`
   - Expected: `model_server_reachable: true`
2. Check Vercel frontend: `https://your-project.vercel.app`
3. Upload a document and test a query.

## Environment Variables Summary

### Render (Flask Backend)
| Variable | Value |
|----------|-------|
| `USE_MODEL_SERVER` | `true` |
| `MODEL_SERVER_URL` | Cloudflare tunnel URL for Ollama |
| `MODEL_NAME` | `vta-assistant` |
| `MODEL_TIMEOUT_SEC` | `60` |
| `MODEL_MAX_TOKENS` | `512` |
| `MODEL_TEMPERATURE` | `0.2` |
| `EMBEDDING_PROVIDER` | `ollama` |
| `OLLAMA_EMBEDDING_MODEL` | `nomic-embed-text` |
| `CLUSTER_INGEST_URL` | Cloudflare tunnel URL for ingest service |
| `NODE_API_URL` | Render Node backend URL |
| `SUPABASE_URL` | Your Supabase URL |
| `SUPABASE_KEY` | Your Supabase anon key |

### Render (Node Backend)
| Variable | Value |
|----------|-------|
| `PORT` | `10000` |
| `SUPABASE_URL` | Your Supabase URL |
| `SUPABASE_KEY` | Your Supabase anon key |

### Vercel (Frontend)
| Variable | Value |
|----------|-------|
| `VTA_BACKEND_URL` | Render Flask backend URL |

## Important Notes

- **Render free tier** sleeps after 15 min of inactivity. Use a paid plan or set up a keep-alive ping.
- **Cloudflare Tunnel** must stay running on the cluster (tmux session `vta-tunnel`).
- **Ollama** must stay running on the cluster (tmux session `vta-model`).
- **Ingest service** must stay running on the cluster (tmux session `vta-ingest`).
- The SSH tunnel is no longer needed once Cloudflare Tunnel is set up.
- All 4 services on the cluster (Ollama, ingest, tunnel, and optionally the Node backend) should run under tmux for persistence.

## Keeping Cluster Services Alive

All services run under tmux. To restart after a cluster reboot:

```bash
# Ollama
tmux new-session -d -s vta-model "OLLAMA_MODELS=/mnt/na1/eecs/srdesign/vta/ollama_models OLLAMA_HOST=0.0.0.0:11434 /mnt/na1/eecs/srdesign/vta/ollama/bin/ollama serve"

# Ingest service
tmux new-session -d -s vta-ingest "/mnt/na1/eecs/srdesign/vta/ingest_service/run.sh"

# Cloudflare tunnel
tmux new-session -d -s vta-tunnel "/mnt/na1/eecs/srdesign/vta/cloudflared tunnel --config /mnt/na1/eecs/srdesign/vta/cloudflared-config.yml run"
```
