# Video and Audio Transcription Feature

## Virtual Teaching Assistant (VTA) - Media Transcription for Google Drive

---

## Overview

The Video and Audio Transcription feature extends the Google Drive integration in the VTA system to support video and audio files. Teachers can now import lecture recordings from their Google Drive, and the VTA will automatically transcribe the speech to text, making it searchable through the VTA chat interface.

This feature enables teachers to upload lecture recordings, guest talks, podcast episodes, and other audio/video content without manual transcription. The VTA uses Gemini 2.0 Flash API for speech-to-text transcription, extracting speaker segments, timestamps, and even tone analysis.

---

## Supported File Types

### Video Files
| Format | MIME Type | Extension |
|--------|----------|-----------|
| MP4 | video/mp4 | .mp4 |
| QuickTime | video/quicktime | .mov |
| WebM | video/webm | .webm |
| AVI | video/x-msvideo | .avi |
| WMV | video/x-ms-wmv | .wmv |
| FLV | video/x-flv | .flv |

### Audio Files
| Format | MIME Type | Extension |
|--------|----------|-----------|
| MP3 | audio/mpeg | .mp3 |
| WAV | audio/wav | .wav |
| M4A | audio/mp4 | .m4a |
| OGG | audio/ogg | .ogg |
| FLAC | audio/flac | .flac |
| AAC | audio/aac | .aac |
| WMA | audio/wma | .wma |

---

## How It Works

### The Workflow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    MEDIA TRANSCRIPTION WORKFLOW                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  1. Teacher connects Google Drive (same as document import)         │
│                                                                      │
│  2. Teacher clicks "Sync from Drive"                                  │
│     → System lists ALL files including videos/audio                     │
│                                                                      │
│  3. Teacher selects video/audio files                                  │
│     → File type is detected automatically                             │
│                                                                      │
│  4. Teacher clicks "Import Selected"                                  │
│     → For video/audio: /drive/media/embed endpoint                   │
│       For documents: /drive/embed endpoint                          │
│                                                                      │
│  5. VTA downloads the file from Google Drive                         │
│                                                                      │
│  6. (For media only) File is sent to Gemini for transcription:         │
│     → Audio is processed through speech-to-text API                   │
│     → Speaker diarization identifies different speakers                 │
│     → Timestamps are added for each segment                          │
│     → Tone/emotion analysis for each segment                         │
│                                                                      │
│  7. Transcribed text is chunked into segments                         │
│                                                                      │
│  8. Each segment gets a vector embedding for semantic search         │
│                                                                      │
│  9. Transcripts and embeddings are stored in database                  │
│                                                                      │
│ 10. Student asks question → VTA searches transcripts                │
│     → Returns relevant segments with timestamps                     │
│     → Shows which video/audio and time the info came from               │
│                                                                      │
└─────────────────────────────────────────────────────────────────────────┘
```

### What Gets Stored

When a video or audio file is transcribed, the following is stored:

| Data | Description |
|------|-------------|
| **Full Transcript** | Complete text of all speech |
| **Segments** | Individual utterances with timestamps |
| **Speaker ID** | Identifies Speaker 1, Speaker 2, etc. |
| **Timestamps** | Start and end time for each segment |
| **Tone Analysis** | Neutral, professional, excited, etc. |
| **Confidence Score** | 0-1 confidence for each segment |
| **Embeddings** | Vector embeddings for semantic search |
| **Metadata** | Duration, language, speaker count, audio quality |

---

## Technical Details

### Files Modified

| File | Changes |
|------|---------|
| `Code/backend/gdrive/oauth.py` | Added video/audio MIME types to file listing, categorization |
| `Code/backend/gdrive/media_processor.py` | New file - handles transcription |
| `Code/backend/app.py` | Added `/drive/media/embed` route |
| `Code/frontend/static/drive-manager.js` | Added media file handling |

### API Endpoints

#### POST /drive/media/embed
Transcribes a video or audio file.

**Request:**
```json
{
  "file_id": "Google Drive file ID",
  "file_name": "lecture1.mp4",
  "mime_type": "video/mp4",
  "course_id": "cpts451"
}
```

**Response:**
```json
{
  "success": true,
  "file_id": "new_file_id",
  "filename": "lecture1.mp4",
  "file_type": "video",
  "duration_seconds": 1200,
  "word_count": 3500,
  "speaker_count": 2,
  "language": "english",
  "audio_quality": "good",
  "transcript": "Full transcript text...",
  "segments": [
    {
      "segment_id": "seg_0000",
      "content": "Hello class, welcome to today's lecture.",
      "start_time": 0,
      "end_time": 15,
      "speaker": "Speaker 1",
      "confidence": 0.92,
      "tone": "professional"
    },
    ...
  ],
  "chunks_processed": 1,
  "embedding_count": 45
}
```

#### POST /drive/media/query
Queries transcribed media for a course.

**Request:**
```json
{
  "query": "question about the lecture content",
  "course_id": "cpts451"
}
```

---

## Scalability

The media transcription feature is designed for scalability:

| Aspect | Design |
|--------|--------|
| **File Size** | Handles files up to ~100MB comfortably |
| **Duration** | Up to 2 hours per file ( Gemini limit) |
| **Chunking** | For longer files, uses sequential processing |
| **Storage** | Only stores transcripts + embeddings, not original files |
| **API Efficiency** | Reuses existing Gemini client from unified_document_processor.py |

### Architecture Philosophy

1. **Reuse Existing Code**: The MediaProcessor imports and uses the GeminiClient from unified_document_processor.py instead of reimplementing.

2. **Chunked Processing**: Large files are processed in chunks to stay within API limits.

3. **Efficient Storage**: Original media files are deleted after transcription. Only transcripts and embeddings are stored.

4. **Semantic Search**: Each transcript segment gets an embedding, enabling semantic search not just keyword matching.

---

## Student Experience

When a student asks a question about a transcribed lecture:

1. The VTA searches both document chunks AND transcript segments
2. Results include citations showing which lecture and timestamp
3. Example response:

```
Based on the lecture from October 15th, the professor discussed 
the capital asset pricing model. At timestamp 12:45, they mentioned:

"The CAPM formula is: expected return equals risk-free rate 
plus beta times the market risk premium."

This comes from "Lecture 12 - CAPM Model.mp4" at 12:45.
```

---

## Security and Privacy

### Data Handling

| Data | Storage Location |
|------|-----------------|
| Original video/audio | Deleted after processing |
| Transcripts | Database (course-scoped) |
| Embeddings | Database (course-scoped) |
| OAuth tokens | Database (encrypted) |

### Privacy Features

1. **No Original Files Stored**: The original video/audio is never stored on the VTA system.
2. **Course Scoping**: All transcripts are scoped to specific courses.
3. **Teacher-Only Import**: Only teachers can import media files.
4. **OAuth Scope**: Only requests read-only Drive access.

---

## Troubleshooting

### Common Issues

**Error: "File too large"**
- The file exceeds the size limit (~100MB)
- Solution: Split the recording into shorter segments

**Error: "Transcription failed"**
- Possible reasons: poor audio quality, non-speech content
- Check the audio_quality field in the response

**Error: "Drive not connected"**
- Need to complete OAuth flow first
- Teacher should click "Link Drive Folder"

### Tips for Best Results

1. **Audio Quality**: Clear audio with minimal background noise produces best transcriptions
2. **File Format**: MP4 (with AAC audio) and MP3 files work best
3. **Multiple Speakers**: The system can identify up to 2-3 speakers reliably
4. **Duration**: Files under 1 hour process faster and more accurately

---

## Example Use Case

A professor records their lectures using Zoom or OBS:

1. Professor uploads recordings to Google Drive
2. In VTA course page, professor enters Drive folder URL
3. Professor clicks "Sync from Drive"
4. Video files (.mp4) appear in the file list alongside PDFs
5. Professor selects the lecture recordings
6. Professor clicks "Import Selected"
7. VTA transcribes each lecture (may take 1-2 minutes per hour of video)
8. Students can now ask "What did the professor say about CAPM?"
9. VTA searches the transcripts and returns relevant segments with timestamps

---

## Summary

The Video and Audio Transcription feature expands the VTA's capabilities to handle multimedia course materials. Teachers can import their lecture recordings directly from Google Drive, and the VTA makes this content searchable through the same chat interface used for documents.

Key benefits:
- No manual transcription needed
- Speaker identification for lectures with multiple people
- Timestamps allow students to find relevant parts quickly
- Semantic search works across both documents and transcripts
- Scalable architecture with efficient storage