# Media Processor for Google Drive Video/Audio Files
# =============================================
#
# This module processes video and audio files from Google Drive:
# - Downloads media files from Google Drive
# - Extracts audio from video files
# - Transcribes using LOCAL Whisper (faster-whisper) - NO API KEY NEEDED!
# - Generates embeddings for semantic search
#
# Version: 4.0.0 - Fully local, free transcription!
# Author: CPT_S 421 Development Team

import os
import logging
import tempfile
import shutil
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION
# ============================================================================

# Check for available transcription options
FASTER_WHISPER_AVAILABLE = False
try:
    from faster_whisper import WhisperModel
    FASTER_WHISPER_AVAILABLE = True
    logger.info("faster-whisper is available - local transcription ready!")
except ImportError:
    logger.warning("faster-whisper not installed")

OPENAI_AVAILABLE = False
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    logger.warning("openai not installed")

GEMINI_AVAILABLE = False
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    logger.warning("google-generativeai not installed")

# Model configuration
WHISPER_MODEL_SIZE = os.environ.get('WHISPER_MODEL', 'base')  # tiny, base, small, medium
GEMINI_EMBEDDING_MODEL = 'models/gemini-embedding-2-preview'

# Supported formats
SUPPORTED_VIDEO_FORMATS = {'.mp4', '.m4v', '.mov', '.avi', '.wmv', '.webm', '.flv', '.mkv', '.3gp'}
SUPPORTED_AUDIO_FORMATS = {'.mp3', '.wav', '.ogg', '.m4a', '.flac', '.aac', '.wma', '.aiff'}


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class MediaSegment:
    """Represents a segment of transcribed media."""
    segment_id: str
    content: str
    start_time: float
    end_time: float
    speaker: str = "Unknown"
    confidence: float = 0.8
    tone: str = "neutral"
    word_count: int = 0
    embedding: Optional[List[float]] = None
    
    def to_dict(self) -> Dict:
        return {
            'segment_id': self.segment_id,
            'content': self.content,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'speaker': self.speaker,
            'confidence': self.confidence,
            'tone': self.tone,
            'word_count': self.word_count
        }


@dataclass
class ProcessedMedia:
    """Represents a fully processed video/audio file."""
    file_id: str
    filename: str
    file_type: str
    mime_type: str
    duration_seconds: float
    full_transcript: str
    segments: List[MediaSegment] = field(default_factory=list)
    language: str = "unknown"
    speaker_count: int = 0
    audio_quality: str = "unknown"
    word_count: int = 0
    processing_time: float = 0.0
    chunks_processed: int = 0
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            'file_id': self.file_id,
            'filename': self.filename,
            'file_type': self.file_type,
            'mime_type': self.mime_type,
            'duration_seconds': self.duration_seconds,
            'full_transcript': self.full_transcript,
            'segments': [s.to_dict() for s in self.segments],
            'language': self.language,
            'speaker_count': self.speaker_count,
            'audio_quality': self.audio_quality,
            'word_count': self.word_count,
            'processing_time': self.processing_time,
            'chunks_processed': self.chunks_processed,
            'metadata': self.metadata
        }


# ============================================================================
# MEDIA PROCESSOR
# ============================================================================

class MediaProcessor:
    """
    Processes video and audio files for transcription.
    
    Priority:
    1. Local Whisper (faster-whisper) - FREE, NO API KEY
    2. OpenAI Whisper - requires API key
    3. Google Gemini - requires API key
    """
    
    def __init__(self, use_local: bool = True, api_key: str = None):
        """Initialize processor."""
        self.use_local = use_local and FASTER_WHISPER_AVAILABLE
        self.local_model = None
        self.openai_client = None
        
        if self.use_local:
            logger.info(f"Loading local Whisper model: {WHISPER_MODEL_SIZE}")
            try:
                self.local_model = WhisperModel(
                    WHISPER_MODEL_SIZE,
                    device="cpu",
                    compute_type="int8"
                )
                logger.info("Local Whisper model loaded successfully!")
            except Exception as e:
                logger.error(f"Failed to load local Whisper: {e}")
                self.use_local = False
        
        # Fallback to cloud if local not available
        if not self.use_local and OPENAI_AVAILABLE:
            if api_key is None:
                api_key = os.environ.get('OPENAI_API_KEY')
            if api_key and api_key != 'YOUR_OPENAI_API_KEY_HERE':
                try:
                    self.openai_client = OpenAI(api_key=api_key)
                    logger.info("Using OpenAI Whisper cloud")
                except:
                    pass
        
        self._temp_files = []
        logger.info(f"MediaProcessor initialized: local={self.use_local}, openai={self.openai_client is not None}")
    
    def process_file(
        self, 
        file_path: str, 
        file_id: str,
        filename: str,
        mime_type: str
    ) -> ProcessedMedia:
        """Process a video or audio file."""
        import time
        start_time = time.time()
        
        # Determine file type
        ext = os.path.splitext(filename)[1].lower()
        is_video = ext in SUPPORTED_VIDEO_FORMATS or mime_type.startswith('video/')
        file_type = 'video' if is_video else 'audio'
        
        logger.info(f"Processing {file_type}: {filename}")
        
        processor = ProcessedMedia(
            file_id=file_id,
            filename=filename,
            file_type=file_type,
            mime_type=mime_type,
            duration_seconds=0,
            full_transcript=""
        )
        
        try:
            # Extract audio from video
            if is_video:
                audio_path = self._extract_audio_from_video(file_path, ext)
                if audio_path:
                    file_path = audio_path
                else:
                    raise ValueError("Failed to extract audio from video")
            
            # Transcribe
            if self.use_local and self.local_model:
                result = self._transcribe_local(file_path)
            elif self.openai_client:
                result = self._transcribe_cloud(file_path, filename)
            else:
                result = {'success': False, 'error': 'No transcription engine available'}
            
            # Update processor
            if result.get('success'):
                processor.full_transcript = result.get('full_text', '')
                processor.segments = self._create_segments(result)
                processor.language = result.get('language_detected', 'english')
                processor.speaker_count = result.get('estimated_speakers', 1)
                processor.word_count = len(processor.full_transcript.split())
                processor.duration_seconds = result.get('duration', 0)
                processor.chunks_processed = 1
            else:
                processor.error = result.get('error', 'Transcription failed')
                
        except Exception as e:
            processor.error = str(e)
            logger.error(f"Processing error: {e}")
        
        processor.processing_time = time.time() - start_time
        logger.info(f"Processing complete in {processor.processing_time:.1f}s")
        
        return processor
    
    def _extract_audio_from_video(self, video_path: str, ext: str) -> Optional[str]:
        """Extract audio from video using ffmpeg."""
        import subprocess
        
        # Find ffmpeg
        ffmpeg_path = shutil.which('ffmpeg')
        if not ffmpeg_path:
            # Try common paths
            for path in [r"C:\ffmpeg\bin\ffmpeg.exe", r"C:\Program Files\ffmpeg\bin\ffmpeg.exe"]:
                if os.path.exists(path):
                    ffmpeg_path = path
                    break
        
        if not ffmpeg_path:
            logger.error("ffmpeg not found")
            return None
        
        try:
            audio_path = video_path + '.wav'
            result = subprocess.run(
                [ffmpeg_path, '-i', video_path, '-vn', '-acodec', 'pcm_s16le', 
                 '-ar', '16000', '-ac', '1', audio_path],
                capture_output=True, text=True, timeout=300
            )
            
            if result.returncode == 0 and os.path.exists(audio_path):
                self._temp_files.append(audio_path)
                logger.info(f"Audio extracted: {audio_path}")
                return audio_path
            else:
                logger.error(f"ffmpeg failed: {result.stderr}")
                return None
        except Exception as e:
            logger.error(f"Audio extraction error: {e}")
            return None
    
    def _transcribe_local(self, audio_path: str) -> Dict[str, Any]:
        """Transcribe using local Whisper."""
        try:
            logger.info("Transcribing with local Whisper...")
            
            segments, info = self.local_model.transcribe(
                audio_path,
                language='en',
                beam_size=5,
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=500)
            )
            
            transcribed_segments = []
            full_text = ""
            duration = 0
            
            for seg in segments:
                transcribed_segments.append({
                    'speaker': 'Speaker 1',
                    'timestamp': f"[{int(seg.start // 60):02d}:{int(seg.start % 60):02d}]",
                    'timestamp_seconds': seg.start,
                    'text': seg.text.strip(),
                    'tone': 'neutral',
                    'confidence': seg.avg_logprob if hasattr(seg, 'avg_logprob') else 0.8,
                    'word_count': len(seg.text.strip().split())
                })
                full_text += seg.text.strip() + " "
                duration = seg.end
            
            logger.info(f"Local Whisper complete: {len(full_text)} chars")
            
            return {
                'success': True,
                'full_text': full_text.strip(),
                'segments': transcribed_segments,
                'duration': duration,
                'language_detected': info.language if hasattr(info, 'language') else 'en',
                'estimated_speakers': 1,
                'audio_quality': 'good'
            }
            
        except Exception as e:
            logger.error(f"Local Whisper error: {e}")
            return {'success': False, 'error': str(e)}
    
    def _transcribe_cloud(self, audio_path: str, filename: str) -> Dict[str, Any]:
        """Transcribe using OpenAI Whisper cloud."""
        try:
            with open(audio_path, 'rb') as f:
                transcript = self.openai_client.audio.transcriptions.create(
                    model='whisper-1',
                    file=f,
                    response_format='verbose_json',
                    timestamp_granularities=['segment']
                )
            
            segments = []
            full_text = ""
            duration = 0
            
            if hasattr(transcript, 'segments'):
                for seg in transcript.segments:
                    segments.append({
                        'speaker': 'Speaker 1',
                        'timestamp': f"[{int(seg.start // 60):02d}:{int(seg.start % 60):02d}]",
                        'timestamp_seconds': seg.start,
                        'text': seg.text.strip(),
                        'tone': 'neutral',
                        'confidence': 0.8,
                        'word_count': len(seg.text.strip().split())
                    })
                    full_text += seg.text.strip() + " "
                    duration = seg.end
            
            return {
                'success': True,
                'full_text': full_text.strip(),
                'segments': segments,
                'duration': duration,
                'language_detected': getattr(transcript, 'language', 'en'),
                'estimated_speakers': 1,
                'audio_quality': 'good'
            }
            
        except Exception as e:
            logger.error(f"Cloud Whisper error: {e}")
            return {'success': False, 'error': str(e)}
    
    def _create_segments(self, result: Dict) -> List[MediaSegment]:
        """Create MediaSegments from result."""
        segments = []
        for i, seg in enumerate(result.get('segments', [])):
            if isinstance(seg, dict):
                segments.append(MediaSegment(
                    segment_id=f"seg_{i:04d}",
                    content=seg.get('text', ''),
                    start_time=seg.get('timestamp_seconds', 0),
                    end_time=seg.get('timestamp_seconds', 0) + 30,
                    speaker=seg.get('speaker', 'Speaker 1'),
                    confidence=seg.get('confidence', 0.8),
                    tone=seg.get('tone', 'neutral'),
                    word_count=seg.get('word_count', 0)
                ))
        return segments
    
    def cleanup(self):
        """Clean up temp files."""
        for tmp in self._temp_files:
            try:
                os.unlink(tmp)
            except:
                pass
        self._temp_files = []