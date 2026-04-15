# Google Drive API Setup Guide

This guide walks you through setting up Google OAuth so teachers can connect their Google Drive to the VTA.

---

## Quick Summary

| Step | Action | Time |
|------|--------|------|
| 1 | Go to Google Cloud Console | 2 min |
| 2 | Create New Project | 1 min |
| 3 | Enable Drive API | 1 min |
| 4 | Create OAuth Credentials | 3 min |
| 5 | Add credentials to .env | 2 min |
| 6 | Test! | 1 min |

---

## Step-by-Step Instructions

### Step 1: Go to Google Cloud Console

Open your browser and go to:
```
https://console.cloud.google.com/
```

### Step 2: Create a New Project

1. Click the project dropdown (top-left, near "Google Cloud")
2. Click **"New Project"**
3. Enter a name like: `Virtual Teaching Assistant`
4. Click **"Create"**
5. Wait for it to finish creating

### Step 3: Enable Google Drive API

1. In the left sidebar, click **"APIs & Services"** → **"Library"**
2. In the search bar, type: `Google Drive API`
3. Click **"Google Drive API"**
4. Click **"Enable"**
5. Wait for it to enable

### Step 4: Create OAuth Credentials

1. In the left sidebar, click **"APIs & Services"** → **"Credentials"**
2. Click **"Create Credentials"** → **"OAuth client ID"**
3. Select Application type: **"Web application"**
4. Fill in the details:

   | Field | Value |
   |-------|-------|
   | Name | `VTA Google Drive` |
   
5. Under **"Authorized redirect URIs"**, click **"Add URI"** and enter:
   ```
   http://localhost:5000/drive/callback
   ```
   (or your actual domain if deployed)

6. Click **"Create"**
7. A popup will show your **Client ID** and **Client Secret**
8. **COPY THESE NOW** - you'll need them!

### Step 5: Add Credentials to Your .env File

Open your `.env` file (or create one in Code/backend/) and add:

```env
# Google OAuth - GET THESE FROM STEP 4!
GOOGLE_CLIENT_ID=your_client_id_here.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your_client_secret_here
GOOGLE_REDIRECT_URI=http://localhost:5000/drive/callback
```

**Important:** Replace the values with what you copied in Step 4!

---

## Step 6: Restart the App and Test

1. Restart your Flask server:
   ```bash
   cd Code/backend
   python app.py
   ```

2. Open your browser and log in as a teacher
3. Go to a course page
4. You should now be able to click **"Link Google Drive"**

---

## What Happens When Teachers Use It

1. Teacher clicks "Link Google Drive"
2. They get redirected to Google to sign in
3. Google asks: "Allow VTA to access your Drive?"
4. Teacher clicks "Allow"
5. They return to the VTA with Drive connected!
6. They can now select files to embed

---

## Troubleshooting

### "Error: Google OAuth not configured"
- Your `.env` file isn't loaded
- Check that the variables are actually set
- Restart the Flask server after adding to .env

### "Error: invalid_client"
- Your Client ID or Secret is wrong
- Double-check for typos

### "Error: redirect_uri_mismatch"
- Your redirect URI doesn't match exactly
- Make sure it matches exactly: `http://localhost:5000/drive/callback`

---

## Notes

- **Your Client ID** ends with `.apps.googleusercontent.com`
- **Your Client Secret** is a longer random string
- The redirect URI must match exactly (including http vs https)
- If you deploy to production, you'll need to add that URL too

---

## Quick Reference

| Credential | Where to Find |
|-----------|-------------|
| Client ID | Google Console → Credentials → OAuth 2.0 → Client ID |
| Client Secret | Same place (click the client to reveal) |

---

*Document Version: 1.0*
*Updated: April 2026*