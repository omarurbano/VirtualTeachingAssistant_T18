# Table Analysis Enhancements Specification

## Target File: `unified_document_processor.py`
## Target Method: `analyze_table` (lines 364-405)

## Current Implementation
The current method provides basic table analysis:
- Summary of what the table contains
- Key insights or patterns
- Column descriptions
- Data quality issues

## Required Enhancements

### 1. Enhanced Prompt Engineering for Detailed Table Analysis
Update the table analysis prompt to request detailed structural analysis:

```python
# Enhanced table analysis prompt
prompt = f"""You are an expert data analyst specializing in table interpretation. Analyze this table comprehensively and provide a detailed analysis in JSON format:

{{
  "summary": "Concise summary of what the table represents and its main purpose",
  "structure": {{
    "row_count": {len(table.rows) if table.rows else 0},
    "column_count": {len(table.rows[0]) if table.rows and table.rows[0] else 0},
    "has_header_row": true/false,
    "has_footer_row": true/false,
    "is_numeric_matrix": true/false,  // True if all cells are numbers
    "table_type": "financial/scientific/survey/schedule/inventory/other"
  }},
  "columns": [
    {{
      "column_index": 0,
      "header": "column header text",
      "data_type": "numeric/integer/float/currency/percentage/date/time/text/categorical/mixed",
      "format_detected": "e.g., $1,234.56, 25%, 2023-01-15, etc.",
      "is_key_column": true/false,  // Likely primary key or identifier
      "is_foreign_key": true/false,  // References another table
      "unique_value_count": estimated_count_or_actual_if_small,
      "null_or_empty_count": count_of_empty_cells,
      "descriptive_statistics": {{
        "mean": numeric_value_or_null,
        "median": numeric_value_or_null,
        "mode": numeric_value_or_null_or_array,
        "std_dev": numeric_value_or_null,
        "min": numeric_value_or_null,
        "max": numeric_value_or_null,
        "q1": numeric_value_or_null,
        "q3": numeric_value_or_null,
        "percentiles": {{"90": value, "95": value, "99": value}}
      }},
      "value_range": {{"min": min_value, "max": max_value}},
      "most_common_values": [{{"value": "value1", "count": count1}}, {{"value": "value2", "count": count2}}],
      "data_quality_issues": ["missing_values", "inconsistent_format", "outliers"],
      "semantic_type": "id/name/description/quantity/price/percentage/rate/score/etc"
    }}
    // Repeat for each column
  ],
  "relationships": [
    {{
      "type": "functional_dependency/correlation/categorical_grouping",
      "description": "description of the relationship",
      "involved_columns": [0, 1, 2],  // column indices
      "strength": "strong/medium/weak",
      "details": "additional details about the relationship"
    }}
  ],
  "patterns_insights": [
    "Specific observations about data patterns",
    "Trends visible in the data",
    "Anomalies or outliers detected",
    "Notable characteristics"
  ],
  "data_quality": {{
    "overall_score": 0.0-1.0,
    "completeness": 0.0-1.0,  // Percentage of non-empty cells
    "consistency": 0.0-1.0,   // Consistency of formats and types
    "accuracy": 0.0-1.0,      // Apparent accuracy based on validity checks
    "issues_found": [
      {{"type": "missing_values", "location": "column 2, rows 5-7", "severity": "medium"}},
      {{"type": "inconsistent_formatting", "location": "column 4", "severity": "low"}}
    ]
  }},
  "suggested_visualizations": ["bar_chart", "line_chart", "pie_chart", "scatter_plot", "heatmap"],
  "potential_use_cases": ["financial_reporting", "inventory_tracking", "survey_analysis", "performance_metrics"],
  "confidence_scores": {{
    "overall": 0.0-1.0,
    "structure_detection": 0.0-1.0,
    "type_detection": 0.0-1.0,
    "relationship_analysis": 0.0-1.0
  }}
}}

Table:
{table_markdown}

Context: {context}"""
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
        
        # Validate and ensure required fields exist with defaults
        if 'summary' not in analysis:
            analysis['summary'] = response.text[:200] + ("..." if len(response.text) > 200 else "")
            
        if 'structure' not in analysis:
            analysis['structure'] = {
                'row_count': len(table.rows) if table.rows else 0,
                'column_count': len(table.rows[0]) if table.rows and table.rows[0] else 0,
                'has_header_row': bool(table.rows) if table.rows else False,
                'has_footer_row': False,
                'is_numeric_matrix': False,
                'table_type': 'unknown'
            }
            
        if 'columns' not in analysis:
            # Generate basic column info from table structure
            analysis['columns'] = []
            if table.rows and len(table.rows) > 0:
                header_row = table.rows[0] if len(table.rows) > 0 else []
                for col_idx, header in enumerate(header_row):
                    analysis['columns'].append({
                        'column_index': col_idx,
                        'header': str(header) if header else '',
                        'data_type': 'unknown',
                        'format_detected': '',
                        'is_key_column': False,
                        'is_foreign_key': False,
                        'unique_value_count': 0,
                        'null_or_empty_count': 0,
                        'descriptive_statistics': {},
                        'value_range': {},
                        'most_common_values': [],
                        'data_quality_issues': [],
                        'semantic_type': 'unknown'
                    })
                    
        if 'relationships' not in analysis:
            analysis['relationships'] = []
            
        if 'patterns_insights' not in analysis:
            analysis['patterns_insights'] = []
            
        if 'data_quality' not in analysis:
            analysis['data_quality'] = {
                'overall_score': 0.5,
                'completeness': 0.5,
                'consistency': 0.5,
                'accuracy': 0.5,
                'issues_found': []
            }
            
        if 'suggested_visualizations' not in analysis:
            analysis['suggested_visualizations'] = []
            
        if 'potential_use_cases' not in analysis:
            analysis['potential_use_cases'] = []
            
        if 'confidence_scores' not in analysis:
            analysis['confidence_scores'] = {
                'overall': 0.5,
                'structure_detection': 0.5,
                'type_detection': 0.5,
                'relationship_analysis': 0.5
            }
    else:
        # Fallback to basic analysis if no JSON found
        analysis = {
            'summary': response.text,
            'structure': {
                'row_count': len(table.rows) if table.rows else 0,
                'column_count': len(table.rows[0]) if table.rows and table.rows[0] else 0,
                'has_header_row': bool(table.rows) if table.rows else False,
                'has_footer_row': False,
                'is_numeric_matrix': False,
                'table_type': 'unknown'
            },
            'columns': [],
            'relationships': [],
            'patterns_insights': [],
            'data_quality': {
                'overall_score': 0.5,
                'completeness': 0.5,
                'consistency': 0.5,
                'accuracy': 0.5,
                'issues_found': []
            },
            'suggested_visualizations': [],
            'potential_use_cases': [],
            'confidence_scores': {
                'overall': 0.5,
                'structure_detection': 0.5,
                'type_detection': 0.5,
                'relationship_analysis': 0.5
            }
        }
except Exception as e:
    logger.error(f"Table analysis JSON parsing error: {e}")
    # Ultimate fallback
    analysis = {
        'summary': response.text,
        'structure': {
            'row_count': len(table.rows) if table.rows else 0,
            'column_count': len(table.rows[0]) if table.rows and table.rows[0] else 0,
            'has_header_row': bool(table.rows) if table.rows else False,
            'has_footer_row': False,
            'is_numeric_matrix': False,
            'table_type': 'unknown'
        },
        'columns': [],
        'relationships': [],
        'patterns_insights': [],
        'data_quality': {
            'overall_score': 0.5,
            'completeness': 0.5,
            'consistency': 0.5,
            'accuracy': 0.5,
            'issues_found': []
        },
        'suggested_visualizations': [],
        'potential_use_cases': [],
        'confidence_scores': {
            'overall': 0.5,
            'structure_detection': 0.5,
            'type_detection': 0.5,
            'relationship_analysis': 0.5
        }
    }
```

### 3. Enhanced Metadata Storage
Update how table metadata is stored in DocumentChunk objects:

In the PDF processing section (around lines 632-638), enhance the metadata:

```python
table_chunk = DocumentChunk(
    content=table_md,
    chunk_type='table',
    source_file=filename,
    document_id=doc_id,
    page_number=page_num,
    table_data=table_md,
    metadata={
        'table_index': table_idx,
        'analysis': analysis.get('summary', ''),
        'rows': len(table.rows),
        'columns': len(table.rows[0]) if table.rows else 0,
        # Enhanced metadata fields
        'table_structure': analysis.get('structure', {}),
        'column_details': analysis.get('columns', []),
        'relationships': analysis.get('relationships', []),
        'patterns_insights': analysis.get('patterns_insights', []),
        'data_quality': analysis.get('data_quality', {}),
        'suggested_visualizations': analysis.get('suggested_visualizations', []),
        'potential_use_cases': analysis.get('potential_use_cases', []),
        'confidence_scores': analysis.get('confidence_scores', {}),
        'has_numeric_data': any(col.get('data_type') in ['numeric', 'integer', 'float', 'currency', 'percentage'] 
                               for col in analysis.get('columns', [])),
        'has_date_data': any(col.get('data_type') in ['date', 'time'] 
                            for col in analysis.get('columns', [])),
        'key_columns': [col.get('column_index') for col in analysis.get('columns', []) 
                       if col.get('is_key_column', False)],
        'column_count': len(analysis.get('columns', [])),
        'header_row_present': analysis.get('structure', {}).get('has_header_row', False)
    }
)
```

Apply equivalent enhancements to the DOCX table processing section (around lines 782-788).

### 4. Enhanced Table-to-Markdown Conversion (Optional Improvement)
Consider enhancing the `_table_to_markdown` and `_docx_table_to_markdown` methods to better preserve formatting information that could aid analysis.

## Implementation Notes

1. **Backward Compatibility**: Ensure existing code that expects the old metadata structure continues to work by maintaining the 'analysis' field with the summary.

2. **Error Handling**: Enhance error handling to gracefully degrade to basic analysis if JSON parsing fails or if certain fields are missing.

3. **Performance Considerations**: The enhanced prompts may increase API usage slightly, but the improved analysis quality justifies this cost.

4. **Testing**: Create test cases with various table types (financial tables, survey data, inventory lists, schedules) to validate the enhancements.

## Expected Outcomes

With these enhancements, the system will be able to:
- Accurately identify column data types and formats
- Detect relationships between columns (functional dependencies, correlations)
- Provide detailed statistical summaries for numeric columns
- Assess data quality and identify issues
- Suggest appropriate visualizations for the data
- Enable more precise relevance scoring for table content
- Support better citation and preview generation for table search results
- Allow users to ask specific questions about table structure and content