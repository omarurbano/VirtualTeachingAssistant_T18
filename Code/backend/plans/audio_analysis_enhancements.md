# Audio Analysis Enhancements Specification

## Target File: `unified_document_processor.py`
## Target Method: `transcribe_audio` (lines 409-470)

## Current Implementation
The current method provides basic audio transcription:
- Transcript with timestamps in [MM:SS] format
- Full text transcription
- Basic segment parsing

## Required Enhancements

### 1. Enhanced Prompt Engineering for Speaker Diarization
Update the transcription prompt to request speaker identification:

```python
# Enhanced transcription prompt
prompt = """You are an expert audio transcription specialist. Provide a detailed transcription with speaker identification:

For each distinct speaker segment, provide:
1. The speaker identifier (Speaker 1, Speaker 2, etc.) 
2. The timestamp (start time) in format [MM:SS] or [HH:MM:SS]
3. The transcribed text for that segment
4. Speech characteristics: tone/emotion (neutral, happy, sad, angry, excited, etc.)
5. Confidence score for the transcription (0-1)

Format your response as a JSON array of segments:
[
  {
    "speaker": "Speaker 1",
    "timestamp": "[00:05]",
    "text": "Hello everyone, welcome to the presentation.",
    "tone": "neutral",
    "confidence": 0.92
  },
  {
    "speaker": "Speaker 2", 
    "timestamp": "[00:15]",
    "text": "Thank you, I'll be discussing the quarterly results.",
    "tone": "professional",
    "confidence": 0.89
  }
]

Additionally, provide:
- Overall audio quality assessment
- Background noise description
- Music or other audio elements detected
- Language detected
- Estimated number of unique speakers"""
```

### 2. Enhanced Response Parsing
Improve the `_parse_transcript` method to handle the enhanced JSON structure:

```python
def _parse_transcript(self, transcript: str) -> List[Dict]:
    """
    Parse transcript text to extract speaker diarization and timestamps.
    
    Args:
        transcript: Raw transcript text (expected JSON format)
        
    Returns:
        List of segment dicts with speaker, timestamp, text, tone, confidence
    """
    segments = []
    
    try:
        # Try to parse as JSON array
        if transcript.strip().startswith('['):
            import json
            parsed_segments = json.loads(transcript)
            
            for seg in parsed_segments:
                # Convert timestamp string to seconds
                timestamp_str = seg.get('timestamp', '').strip('[]')
                timestamp_seconds = self._parse_timestamp_to_seconds(timestamp_str)
                
                segments.append({
                    'speaker': seg.get('speaker', 'Unknown'),
                    'timestamp': timestamp_str,
                    'timestamp_seconds': timestamp_seconds,
                    'text': seg.get('text', '').strip(),
                    'tone': seg.get('tone', 'neutral'),
                    'confidence': float(seg.get('confidence', 0.8)),
                    'word_count': len(seg.get('text', '').split())
                })
        else:
            # Fallback to original parsing for non-JSON responses
            pattern = r'(?:\[?(\d{1,2}:\d{2})(?::\d{2})?\]?)\s*(.+?)(?=(?:\[?\d{1,2}:\d{2})|$)'
            matches = re.findall(pattern, transcript, re.DOTALL)
            
            for timestamp, text in matches:
                segments.append({
                    'speaker': 'Speaker 1',  # Default when no speaker info
                    'timestamp': timestamp,
                    'timestamp_seconds': self._parse_timestamp_to_seconds(timestamp),
                    'text': text.strip(),
                    'tone': 'neutral',
                    'confidence': 0.8,  # Default confidence
                    'word_count': len(text.split())
                })
                
    except Exception as e:
        logger.error(f"Transcript parsing error: {e}")
        # Ultimate fallback: treat as single segment
        segments.append({
            'speaker': 'Speaker 1',
            'timestamp': '[00:00]',
            'timestamp_seconds': 0,
            'text': transcript.strip(),
            'tone': 'neutral',
            'confidence': 0.5,
            'word_count': len(transcript.split())
        })
    
    return segments

def _parse_timestamp_to_seconds(self, timestamp_str: str) -> float:
    """Convert timestamp string like 'MM:SS' or 'HH:MM:SS' to seconds."""
    try:
        parts = timestamp_str.split(':')
        if len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        elif len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        else:
            return 0.0
    except:
        return 0.0
```

### 3. Enhanced Metadata Storage
Update how audio metadata is stored in DocumentChunk objects:

In the audio processing section (around lines 894-908), enhance the metadata:

```python
chunk = DocumentChunk(
    content=segment['text'],
    chunk_type='audio',
    source_file=filename,
    document_id=doc_id,
    timestamp=segment['timestamp_seconds'],  # Store as seconds for easy comparison
    metadata={
        'timestamp_str': segment['timestamp'],
        'segment_index': len(chunks),
        'speaker': segment.get('speaker', 'Unknown'),
        'tone': segment.get('tone', 'neutral'),
        'confidence': segment.get('confidence', 0.8),
        'word_count': segment.get('word_count', 0),
        'is_speaker_change': len(chunks) > 0 and 
                           chunks[-1].metadata.get('speaker') != segment.get('speaker', 'Unknown')
    }
)
```

Also enhance the full transcript chunk metadata:

```python
# Also create a full transcript chunk with speaker information
full_transcript = DocumentChunk(
    content=result['full_text'],
    chunk_type='audio',
    source_file=filename,
    document_id=doc_id,
    metadata={
        'is_full_transcript': True,
        'speaker_segments': result.get('segments', []),
        'unique_speakers': list(set(seg.get('speaker', 'Unknown') for seg in result.get('segments', []))),
        'diarization_success': len(result.get('segments', [])) > 1 and 
                              len(set(seg.get('speaker', 'Unknown') for seg in result.get('segments', []))) > 1
    }
)
```

### 4. Enhanced Audio Analysis Information
Modify the `transcribe_audio` method to return additional analysis:

```python
return {
    'transcript': response.text,
    'segments': transcript_segments,
    'success': True,
    'full_text': '\n'.join([s['text'] for s in transcript_segments]),
    # Enhanced analysis fields
    'audio_quality': self._extract_audio_quality(response.text),  # New helper method
    'background_noise': self._extract_background_noise(response.text),  # New helper method
    'language_detected': self._extract_language(response.text),  # New helper method
    'estimated_speakers': len(set(seg.get('speaker', 'Unknown') for seg in transcript_segments)),
    'speech_rate_wpm': self._calculate_speech_rate(transcript_segments)  # Words per minute
}
```

Add helper methods to extract additional information from the Gemini response:

```python
def _extract_audio_quality(self, response_text: str) -> str:
    """Extract audio quality assessment from Gemini response."""
    # Simple keyword extraction - could be enhanced with more sophisticated parsing
    quality_indicators = ['clear', 'muffled', 'distorted', 'noisy', 'clean', 'poor', 'excellent', 'good', 'fair']
    response_lower = response_text.lower()
    for indicator in quality_indicators:
        if indicator in response_lower:
            return indicator
    return 'unknown'

def _extract_background_noise(self, response_text: str) -> str:
    """Extract background noise description from Gemini response."""
    noise_indicators = ['background noise', 'static', 'hiss', 'hum', 'echo', 'reverb', 'music']
    response_lower = response_text.lower()
    for indicator in noise_indicators:
        if indicator in response_lower:
            return indicator
    return 'none detected'

def _extract_language(self, response_text: str) -> str:
    """Extract language detection from Gemini response."""
    # Look for language mentions
    languages = ['english', 'spanish', 'french', 'german', 'chinese', 'japanese', 'portuguese']
    response_lower = response_text.lower()
    for lang in languages:
        if lang in response_lower:
            return lang
    return 'unknown'

def _calculate_speech_rate(self, segments: List[Dict]) -> float:
    """Calculate words per minute across all segments."""
    if not segments:
        return 0.0
    
    total_words = sum(seg.get('word_count', 0) for seg in segments)
    if total_words == 0:
        return 0.0
        
    # Get time span
    timestamps = [seg.get('timestamp_seconds', 0) for seg in segments if seg.get('timestamp_seconds') is not None]
    if not timestamps or max(timestamps) == min(timestamps):
        return 0.0
        
    duration_minutes = (max(timestamps) - min(timestamps)) / 60.0
    if duration_minutes == 0:
        return 0.0
        
    return total_words / duration_minutes
```

## Implementation Notes

1. **Backward Compatibility**: Ensure existing code that expects the old metadata structure continues to work.

2. **Error Handling**: Enhance error handling to gracefully degrade to basic transcription if JSON parsing fails.

3. **Performance Considerations**: The enhanced prompts may increase API usage slightly, but the improved analysis quality justifies this cost.

4. **Testing**: Create test cases with various audio scenarios (single speaker, multiple speakers, background noise, different accents) to validate the enhancements.

## Expected Outcomes

With these enhancements, the system will be able to:
- Accurately identify different speakers in audio content
- Provide detailed speech characteristics (tone, emotion)
- Enable speaker-specific search and retrieval
- Support better citation and preview generation for audio search results
- Provide audio quality metrics for filtering and ranking