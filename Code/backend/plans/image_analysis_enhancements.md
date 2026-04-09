# Image Analysis Enhancements Specification

## Target File: `unified_document_processor.py`
## Target Method: `analyze_image_with_vision` (lines 312-360)

## Current Implementation
The current method provides basic image analysis:
- Visual description
- Text content (OCR)
- Keywords for search
- Raw response storage

## Required Enhancements

### 1. Enhanced Prompt Engineering
Update the prompt to request more detailed structured analysis:

```python
# Detailed analysis prompt
prompt = """You are an expert image analyst with deep understanding of charts, graphs, and technical diagrams. Provide a comprehensive analysis in JSON format:

{
  "description": "Detailed description of all visual elements, layout, and composition",
  "text_content": {
    "raw_text": "All text visible in the image (transcribed exactly)",
    "text_blocks": [
      {
        "text": "text string",
        "confidence": 0.95,  // OCR confidence score (0-1)
        "bounding_box": [x1, y1, x2, y2],  // Normalized coordinates (0-1)
        "font_size_estimate": "small/medium/large",
        "is_header": true/false
      }
    ]
  },
  "data_visualization": {
    "chart_type": "bar/line/pie/scatter/area/histogram/boxplot/unknown",
    "data_points": [
      {
        "label": "category or x-value",
        "value": numeric_value,
        "series": "series name if applicable"
      }
    ],
    "axes": {
      "x_axis": {
        "label": "axis label",
        "type": "categorical/numeric/date",
        "range": [min, max]  // for numeric axes
      },
      "y_axis": {
        "label": "axis label", 
        "type": "categorical/numeric/date",
        "range": [min, max]  // for numeric axes
      }
    },
    "legends": [
      {
        "title": "legend title",
        "items": ["item1", "item2"]
      }
    ],
    "title": "chart or graph title",
    "caption": "caption or description below chart",
    "trends": ["increasing", "decreasing", "peak at X", "outlier at Y"],
    "statistics_visible": ["mean: 5.2", "std: 1.3"]  // Any statistics shown in chart
  },
  "context": {
    "document_type": "research paper/presentation slide/report/dashboard/other",
    "subject_area": "finance/engineering/medicine/etc if detectable",
    "likely_purpose": "what this image is likely used for"
  },
  "search_keywords": ["keyword1", "keyword2", "keyword3", "keyword4", "keyword5"],
  "confidence_scores": {
    "overall": 0.9,
    "chart_interpretation": 0.85,
    "text_extraction": 0.95
  }
}"""
```

### 2. Enhanced Response Parsing
Improve the JSON parsing to handle the enhanced structure:

```python
# Try to parse as JSON, fallback to plain text
try:
    # Find JSON in response
    json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
    if json_match:
        analysis = json.loads(json_match.group())
        
        # Validate and enhance the analysis structure
        if 'text_content' not in analysis:
            analysis['text_content'] = {
                'raw_text': analysis.get('description', ''),
                'text_blocks': []
            }
            
        if 'data_visualization' not in analysis:
            analysis['data_visualization'] = {
                'chart_type': 'unknown',
                'data_points': [],
                'axes': {},
                'legends': [],
                'title': '',
                'caption': '',
                'trends': [],
                'statistics_visible': []
            }
            
        if 'context' not in analysis:
            analysis['context'] = {
                'document_type': 'unknown',
                'subject_area': 'unknown',
                'likely_purpose': 'unknown'
            }
    else:
        analysis = {
            'description': response.text, 
            'text_content': {'raw_text': '', 'text_blocks': []},
            'data_visualization': {'chart_type': 'unknown', 'data_points': [], 'axes': {}, 'legends': [], 'title': '', 'caption': '', 'trends': [], 'statistics_visible': []},
            'context': {'document_type': 'unknown', 'subject_area': 'unknown', 'likely_purpose': 'unknown'},
            'keywords': []
        }
except:
    analysis = {
        'description': response.text, 
        'text_content': {'raw_text': '', 'text_blocks': []},
        'data_visualization': {'chart_type': 'unknown', 'data_points': [], 'axes': {}, 'legends': [], 'title': '', 'caption': '', 'trends': [], 'statistics_visible': []},
        'context': {'document_type': 'unknown', 'subject_area': 'unknown', 'likely_purpose': 'unknown'},
        'keywords': []
    }
```

### 3. Enhanced Metadata Storage
Update how image metadata is stored in DocumentChunk objects:

In the PDF processing section (around lines 665-678), enhance the metadata:

```python
img_chunk = DocumentChunk(
    content=f"Image: {description}. Keywords: {', '.join(keywords)}",
    chunk_type='image',
    source_file=filename,
    document_id=doc_id,
    page_number=page_num,
    image_data=base64.b64encode(img_data).decode('utf-8'),
    metadata={
        'image_index': img_idx,
        'description': description,
        'keywords': keywords,
        'analysis': analysis.get('raw_response', ''),
        # Enhanced metadata fields
        'chart_type': analysis.get('data_visualization', {}).get('chart_type', 'unknown'),
        'text_blocks': analysis.get('text_content', {}).get('text_blocks', []),
        'data_points': analysis.get('data_visualization', {}).get('data_points', []),
        'axes_info': analysis.get('data_visualization', {}).get('axes', {}),
        'legends_info': analysis.get('data_visualization', {}).get('legends', []),
        'title': analysis.get('data_visualization', {}).get('title', ''),
        'caption': analysis.get('data_visualization', {}).get('caption', ''),
        'trends': analysis.get('data_visualization', {}).get('trends', []),
        'statistics_visible': analysis.get('data_visualization', {}).get('statistics_visible', []),
        'document_type': analysis.get('context', {}).get('document_type', 'unknown'),
        'subject_area': analysis.get('context', {}).get('subject_area', 'unknown'),
        'likely_purpose': analysis.get('context', {}).get('likely_purpose', 'unknown'),
        'confidence_scores': analysis.get('confidence_scores', {}),
        'has_chart_data': len(analysis.get('data_visualization', {}).get('data_points', [])) > 0,
        'has_text_content': len(analysis.get('text_content', {}).get('text_blocks', [])) > 0
    }
)
```

### 4. Similar Enhancements for DOCX Image Processing
Apply equivalent enhancements to the DOCX image processing section (around lines 806-822).

## Implementation Notes

1. **Backward Compatibility**: Ensure existing code that expects the old metadata structure continues to work by maintaining backward compatibility where possible.

2. **Error Handling**: Enhance error handling to gracefully degrade to basic analysis if JSON parsing fails or if certain fields are missing.

3. **Performance Considerations**: The enhanced prompts may increase API usage slightly, but the improved analysis quality justifies this cost.

4. **Testing**: Create test cases with various chart types (bar, line, pie, scatter) and images with different text layouts to validate the enhancements.

## Expected Outcomes

With these enhancements, the system will be able to:
- Accurately interpret chart data and extract numerical values
- Provide detailed text localization with confidence scores
- Understand chart context and purpose
- Enable more precise relevance scoring for image content
- Support better citation and preview generation for image search results