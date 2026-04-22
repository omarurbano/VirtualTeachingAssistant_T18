# API Keys Setup Guide

## Virtual Teaching Assistant (VTA) - Environment Configuration

---

## Overview

This guide explains how to set up the required API keys in your `.env` file for the VTA system to function properly. The system uses multiple APIs for different features.

---

## Required API Keys

| Feature | API Provider | Key Name | Status |
|---------|--------------|----------|--------|
| Document Embeddings | Google Gemini | `GOOGLE_API_KEY` | Required |
| Video/Audio Transcription | OpenAI Whisper | `OPENAI_API_KEY` | Required for media |
| Google Drive Integration | Google Cloud | `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | Required for Drive |

---

## .env File Setup

### Step 1: Create the .env File

Create a file named `.env` in the `Code/backend/` directory (same folder as `app.py`).

### Step 2: Add the Following Configuration

Copy and paste the template below into your `.env` file:

```env
# =============================================================================
# GOOGLE API KEYS (Required for document embeddings and Gemini AI)
# =============================================================================
# Get this from: https://aistudio.google.com/app/apikey
GOOGLE_API_KEY=your_google_api_key_here

# =============================================================================
# OPENAI API KEY (Required for video/audio transcription with Whisper)
# =============================================================================
# Get this from: https://platform.openai.com/api-keys
OPENAI_API_KEY=your_openai_api_key_here

# =============================================================================
# GOOGLE OAUTH (Required for Google Drive integration)
# =============================================================================
# Get these from: https://console.cloud.google.com/apis/credentials
GOOGLE_CLIENT_ID=your_client_id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your_client_secret
GOOGLE_REDIRECT_URI=http://localhost:5000/drive/callback

# =============================================================================
# NODE.JS API (Internal - usually no need to change)
# =============================================================================
NODE_API_URL=http://localhost:3000

# =============================================================================
# FLASK SECRET KEY (Session security)
# =============================================================================
SECRET_KEY=your-secret-key-change-in-production
```

---

## How to Get Each API Key

### 1. Google Gemini API Key (GOOGLE_API_KEY)

**Purpose:** Used for document embeddings, text generation, and AI features.

**Steps to get:**

1. **Go to Google AI Studio**
   - Visit: https://aistudio.google.com/app/apikey
   
2. **Sign in with your Google account**

3. **Click "Create API Key"**

4. **Select or create a new Google Cloud project**
   - If you don't have one, click "Create a new project"
   - Give it a name (e.g., "VTA Project")

5. **Copy the API key**

6. **Add billing (recommended)**
   - Go to: https://console.cloud.google.com/billing
   - Link a billing account
   - This gives you $300 free credits
   - Without billing, free tier is very limited

7. **Paste the key in your .env file:**
   ```
   GOOGLE_API_KEY=AIzaSyC...
   ```

---

### 2. OpenAI API Key (OPENAI_API_KEY)

**Purpose:** Used for Whisper transcription of video and audio files.

**Steps to get:**

1. **Go to OpenAI Platform**
   - Visit: https://platform.openai.com/api-keys
   
2. **Sign up or sign in**
   - Click "Sign up" if you don't have an account
   - You can use Google or Microsoft login

3. **Verify your email**
   - Check your inbox and click the verification link

4. **Go to API Keys page**
   - Click your profile picture in the top right
   - Select "API keys" from the dropdown

5. **Create a new API key**
   - Click "Create new secret key"
   - Give it a name (e.g., "VTA Transcription")
   - **IMPORTANT:** Copy the key immediately - it won't be shown again!

6. **Paste the key in your .env file:**
   ```
   OPENAI_API_KEY=sk-proj-...
   ```

**Cost Information:**
- Whisper is very affordable
- $0.006 per minute of audio (~ $0.36 per hour)
- New accounts get $5-10 free credits
- Check usage at: https://platform.openai.com/usage

---

### 3. Google OAuth Credentials (GOOGLE_CLIENT_ID & GOOGLE_CLIENT_SECRET)

**Purpose:** Allows teachers to connect their Google Drive to import files.

**Steps to get:**

1. **Go to Google Cloud Console**
   - Visit: https://console.cloud.google.com/
   
2. **Create or select a project**
   - Click the project dropdown in the top left
   - Select or create a new project

3. **Enable the Google Drive API**
   - Go to "APIs & Services" > "Library"
   - Search for "Google Drive API"
   - Click on it and click "Enable"

4. **Create OAuth 2.0 credentials**
   - Go to "APIs & Services" > "Credentials"
   - Click "Create Credentials" > "OAuth client ID"
   
5. **Configure the OAuth consent screen (first time only)**
   - Click "Configure consent screen"
   - Choose "External"
   - Fill in:
     - App name: "VTA Assistant"
     - User support email: your email
     - Developer contact: your email
   - Click "Save and continue" through the rest
   
6. **Create the OAuth client**
   - Go back to "Create Credentials" > "OAuth client ID"
   - Application type: "Web application"
   - Name: "VTA Web App"
   - Authorized redirect URIs: Click "Add URI" and enter:
     ```
     http://localhost:5000/drive/callback
     ```
   - Click "Create"

7. **Copy the credentials**
   - From the success screen, copy:
     - **Client ID** (ends in .apps.googleusercontent.com)
     - **Client Secret** (the random string)

8. **Paste in your .env file:**
   ```
   GOOGLE_CLIENT_ID=123456789-abc.apps.googleusercontent.com
   GOOGLE_CLIENT_SECRET=AbCdEfGhIjKlMnOpQrStUvWx
   GOOGLE_REDIRECT_URI=http://localhost:5000/drive/callback
   ```

---

## Quick Setup Checklist

- [ ] Created `Code/backend/.env` file
- [ ] Added `GOOGLE_API_KEY` (from aistudio.google.com)
- [ ] Added `OPENAI_API_KEY` (from platform.openai.com/api-keys)
- [ ] Added `GOOGLE_CLIENT_ID` (from console.cloud.google.com)
- [ ] Added `GOOGLE_CLIENT_SECRET`
- [ ] Installed required packages:
  ```bash
  pip install openai pydub moviepy
  ```

---

## Testing Your Setup

### Test Google API:
```bash
cd Code/backend
python -c "import google.generativeai as genai; genai.configure(api_key='YOUR_KEY'); print('Google API OK')"
```

### Test OpenAI API:
```bash
cd Code/backend  
python -c "from openai import OpenAI; client = OpenAI(api_key='YOUR_KEY'); print('OpenAI API OK')"
```

---

## Troubleshooting

### "GOOGLE_API_KEY not set" error
- Make sure the .env file is in `Code/backend/` folder
- Restart Flask after updating .env

### "OpenAI not installed" error
- Run: `pip install openai`

### "Whisper transcription failed" error
- Check your OpenAI API key is correct
- Check you have credits: https://platform.openai.com/usage

### Google Drive not connecting
- Verify GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET are correct
- Make sure Google Drive API is enabled in Cloud Console

---

## Security Notes

1. **Never commit .env to git** - Add `.env` to your `.gitignore` file
2. **Keep keys private** - Don't share your API keys
3. **Rotate keys periodically** - Generate new keys if compromised
4. **Set spending limits** - In both Google Cloud and OpenAI dashboards

---

## Summary of Where to Get Keys

| Key | URL |
|-----|-----|
| GOOGLE_API_KEY | https://aistudio.google.com/app/apikey |
| OPENAI_API_KEY | https://platform.openai.com/api-keys |
| GOOGLE_CLIENT_ID/SECRET | https://console.cloud.google.com/apis/credentials |