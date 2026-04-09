"""
Multi-File RAG System - Multimodal Document Processor
=====================================================

This module handles complex PDF documents with multiple content types:
- Plain text extraction
- Table extraction with structure preservation
- Image extraction with OCR
- Caption detection and association
- Position tracking for all elements

This enables the RAG system to handle documents like academic papers,
technical manuals, and reports that contain mixed media.

Author: CPT_S 421 Development Team
Version: 1.1.0
Created: 2026-02-22

Based on concepts from: 03b_OCR_Pipelines notebook
"""

# ============================================================================
# STANDARD LIBRARY IMPORTS
# ============================================================================

# Import os for file path operations
import os

# Import json for serialization
import json

# Import logging for structured logging
import logging

# Import base64 for image encoding
import base64

# Import io for byte handling
import io

# Import hashlib for generating unique IDs
import hashlib

# Import tempfile for temporary file handling
import tempfile

# Import datetime for timestamp tracking
from datetime import datetime

# ============================================================================
# TYPING IMPORTS
# ============================================================================

# Import typing for type hints
from typing import List, Dict, Optional, Any, Union, Tuple

# ============================================================================
# THIRD-PARTY LIBRARY IMPORTS
# ============================================================================

# Try to import required libraries for multimodal processing

# Unstructured library for PDF partitioning
try:
    from unstructured.partition.pdf import partition_pdf
    from unstructured.elements import Text, Table, Image, NarrativeText, Title, Header, Footer
    UNSTRUCTURED_AVAILABLE = True
except ImportError:
    UNSTRUCTURED_AVAILABLE = False
    logging.warning("unstructured not available. Install with: pip install unstructured")

# Try to import PDF libraries
try:
    from pypdf import PdfReader
    PYPDF_AVAILABLE = True
except ImportError:
    PYPDF_AVAILABLE = False
    logging.warning("pypdf not available. Install with: pip install pypdf")

# Try to import OCR
try:
    import pytesseract
    from PIL import Image as PILImage
    PYTESSERACT_AVAILABLE = True
except ImportError:
    PYTESSERACT_AVAILABLE = False
    logging.warning("pytesseract not available. Install with: pip install pytesseract")

# Try to import image handling
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    logging.warning("Pillow not available. Install with: pip install Pillow")

# Try to import LangChain for document handling
LANGCHAIN_AVAILABLE = False
try:
    from langchain_core.documents import Document
    LANGCHAIN_AVAILABLE = True
except ImportError:
    try:
        from langchain.schema import Document
        LANGCHAIN_AVAILABLE = True
    except ImportError:
        try:
            from langchain_community.schema import Document
            LANGCHAIN_AVAILABLE = True
        except ImportError:
            logging.warning("langchain not available")

# Set multimodal availability based on unstructured
MULTIMODAL_AVAILABLE = UNSTRUCTURED_AVAILABLE and LANGCHAIN_AVAILABLE

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

# Configure logging for this module
logger = logging.getLogger(__name__)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# ============================================================================
# CONSTANTS
# ============================================================================

# Element types for multimodal documents
ELEMENT_TYPE_TEXT = 'text'
ELEMENT_TYPE_TABLE = 'table'
ELEMENT_TYPE_IMAGE = 'image'
ELEMENT_TYPE_TITLE = 'title'
ELEMENT_TYPE_HEADER = 'header'
ELEMENT_TYPE_FOOTER = 'footer'
ELEMENT_TYPE_OCR = 'ocr'  # Text extracted from images via OCR

# Supported strategies for PDF partitioning
PARTITION_STRATEGY_AUTO = 'auto'
PARTITION_STRATEGY_FAST = 'fast'
PARTITION_STRATEGY_HI_RES = 'hi_res'
PARTITION_STRATEGY_OCR_ONLY = 'ocr_only'

# ============================================================================
# DATA CLASSES
# ============================================================================

class MultimodalElement:
    """
    Represents a single element extracted from a multimodal document.
    
    This class encapsulates all information about an element including:
    - Content type (text, table, image, OCR)
    - The actual content (text, table data, image)
    - Position information (page, coordinates)
    - Metadata (captions, associations)
    
    Attributes:
        element_id: Unique identifier for this element
        element_type: Type of element (text, table, image, ocr)
        content: The actual content
        page_number: Page where element was found
        coordinates: Position coordinates (x1, y1, x2, y2)
        source_file: Source file name
        caption: Associated caption (if any)
        metadata: Additional metadata dictionary
    """
    
    def __init__(
        self,
        element_id: str,
        element_type: str,
        content: Any,
        page_number: int = 1,
        coordinates: Tuple[int, int, int, int] = None,
        source_file: str = '',
        caption: str = None,
        metadata: Dict = None
    ):
        """
        Initialize a MultimodalElement.
        
        Args:
            element_id: Unique identifier
            element_type: Type of element
            content: The content (text, table, image data)
            page_number: Page number (1-indexed)
            coordinates: Bounding box (x1, y1, x2, y2)
            source_file: Source file name
            caption: Associated caption
            metadata: Additional metadata
        """
        self.element_id = element_id
        self.element_type = element_type
        self.content = content
        self.page_number = page_number
        self.coordinates = coordinates or (0, 0, 0, 0)
        self.source_file = source_file
        self.caption = caption
        self.metadata = metadata or {}
        
        # Generate hash for uniqueness
        self._hash = hashlib.md5(
            f"{source_file}_{page_number}_{element_type}_{element_id}".encode()
        ).hexdigest()[:16]
    
    def get_location_string(self) -> str:
        """
        Get human-readable location string.
        
        Returns:
            Location string (e.g., "Page 5, Position (100, 200)")
        """
        location = f"Page {self.page_number}"
        
        if self.coordinates and self.coordinates != (0, 0, 0, 0):
            location += f", Region ({self.coordinates[0]}, {self.coordinates[1]})"
        
        if self.caption:
            location += f", Caption: {self.caption[:30]}..."
        
        return location
    
    def to_dict(self) -> Dict:
        """
        Convert to dictionary for serialization.
        
        Returns:
            Dictionary representation
        """
        # Handle image content (convert to base64 or skip)
        content_repr = self.content
        if self.element_type == ELEMENT_TYPE_IMAGE:
            if isinstance(self.content, bytes):
                content_repr = f"<image: {len(self.content)} bytes>"
            elif isinstance(self.content, str):
                content_repr = f"<image path: {self.content}>"
        
        return {
            'element_id': self.element_id,
            'element_type': self.element_type,
            'content': content_repr,
            'page_number': self.page_number,
            'coordinates': self.coordinates,
            'source_file': self.source_file,
            'caption': self.caption,
            'location': self.get_location_string(),
            'metadata': self.metadata
        }
    
    def to_langchain_document(self) -> Document:
        """
        Convert to LangChain Document for RAG pipeline.
        
        Returns:
            LangChain Document with enhanced metadata
        """
        # Create content string
        if self.element_type == ELEMENT_TYPE_TABLE:
            # For tables, keep the structured representation
            if isinstance(self.content, dict):
                content_str = json.dumps(self.content)
            else:
                content_str = str(self.content)
        elif self.element_type == ELEMENT_TYPE_IMAGE:
            # For images, use OCR text if available
            content_str = self.metadata.get('ocr_text', '[Image content - see OCR text]')
        else:
            content_str = str(self.content)
        
        # Build metadata
        metadata = {
            'element_id': self.element_id,
            'element_type': self.element_type,
            'page_number': self.page_number,
            'coordinates': self.coordinates,
            'source_file': self.source_file,
            'caption': self.caption,
            'location': self.get_location_string(),
            **{f"meta_{k}": v for k, v in self.metadata.items()}
        }
        
        return Document(
            page_content=content_str,
            metadata=metadata
        )


class TableData:
    """
    Represents extracted table data with structure.
    
    This class stores table content in both human-readable and
    machine-parseable formats.
    
    Attributes:
        table_id: Unique identifier
        headers: Column headers
        rows: Table rows (list of lists)
        page_number: Page where table was found
        caption: Table caption (if any)
    """
    
    def __init__(
        self,
        table_id: str,
        headers: List[str] = None,
        rows: List[List[str]] = None,
        page_number: int = 1,
        caption: str = None
    ):
        """
        Initialize TableData.
        
        Args:
            table_id: Unique identifier
            headers: Column headers
            rows: Data rows
            page_number: Page number
            caption: Table caption
        """
        self.table_id = table_id
        self.headers = headers or []
        self.rows = rows or []
        self.page_number = page_number
        self.caption = caption
    
    def to_markdown(self) -> str:
        """
        Convert table to Markdown format.
        
        Returns:
            Markdown-formatted table string
        """
        if not self.headers and not self.rows:
            return ""
        
        # Build markdown table
        lines = []
        
        # Add caption if available
        if self.caption:
            lines.append(f"**Table: {self.caption}**\n")
        
        # Add headers
        if self.headers:
            lines.append("| " + " | ".join(self.headers) + " |")
            lines.append("| " + " | ".join(["---"] * len(self.headers)) + " |")
        
        # Add rows
        for row in self.rows:
            lines.append("| " + " | ".join(str(cell) for cell in row) + " |")
        
        return "\n".join(lines)
    
    def to_dict(self) -> Dict:
        """
        Convert to dictionary.
        
        Returns:
            Dictionary representation
        """
        return {
            'table_id': self.table_id,
            'headers': self.headers,
            'rows': self.rows,
            'page_number': self.page_number,
            'caption': self.caption,
            'markdown': self.to_markdown()
        }


# ============================================================================
# MAIN PROCESSOR CLASS
# ============================================================================

class MultimodalDocumentProcessor:
    """
    Processes complex PDF documents with multiple content types.
    
    This processor can extract and handle:
    - Plain text from PDF
    - Tables with structure preservation
    - Images with position tracking
    - OCR text from images
    - Captions and their associated elements
    
    The processor maintains detailed position information for each
    element, enabling precise citation in the RAG pipeline.
    
    Example:
        >>> processor = MultimodalDocumentProcessor()
        >>> elements = processor.process_pdf("document.pdf")
        >>> for el in elements:
        ...     print(f"{el.element_type}: {el.get_location_string()}")
    """
    
    def __init__(
        self,
        extract_images: bool = True,
        extract_tables: bool = True,
        ocr_images: bool = True,
        strategy: str = PARTITION_STRATEGY_HI_RES,
        infer_table_structure: bool = True
    ):
        """
        Initialize the MultimodalDocumentProcessor.
        
        Args:
            extract_images: Whether to extract images from PDF
            extract_tables: Whether to extract tables
            ocr_images: Whether to run OCR on extracted images
            strategy: Partitioning strategy to use
            infer_table_structure: Whether to infer table structure
        """
        self.extract_images = extract_images
        self.extract_tables = extract_tables
        self.ocr_images = ocr_images
        self.strategy = strategy
        self.infer_table_structure = infer_table_structure
        
        # Check availability
        self._check_dependencies()
        
        # Element counter
        self._element_counter = 0
        
        logger.info(f"MultimodalDocumentProcessor initialized")
        logger.info(f"  Extract images: {extract_images}")
        logger.info(f"  Extract tables: {extract_tables}")
        logger.info(f"  OCR images: {ocr_images}")
        logger.info(f"  Strategy: {strategy}")
    
    def _check_dependencies(self):
        """
        Check if required dependencies are available.
        """
        if not UNSTRUCTURED_AVAILABLE:
            logger.warning("unstructured library not available. PDF processing will be limited.")
        
        if self.ocr_images and not PYTESSERACT_AVAILABLE:
            logger.warning("pytesseract not available. OCR will be disabled.")
            self.ocr_images = False
        
        if not PIL_AVAILABLE:
            logger.warning("Pillow not available. Image processing will be limited.")
    
    def _generate_element_id(self) -> str:
        """
        Generate a unique element ID.
        
        Returns:
            Unique element ID string
        """
        self._element_counter += 1
        return f"elem_{self._element_counter:06d}"
    
    def process_pdf(self, file_path: str) -> List[MultimodalElement]:
        """
        Process a PDF file and extract all elements.
        
        This is the main method that orchestrates the extraction
        of text, tables, and images from a PDF document.
        
        Args:
            file_path: Path to the PDF file
            
        Returns:
            List of MultimodalElement objects
            
        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If PDF processing fails
        """
        # Validate file exists
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"PDF file not found: {file_path}")
        
        logger.info(f"Processing PDF: {file_path}")
        
        # Reset counter for new document
        self._element_counter = 0
        
        # Get file info
        file_name = os.path.basename(file_path)
        
        elements = []
        
        # Check if unstructured is available
        if UNSTRUCTURED_AVAILABLE:
            elements = self._process_with_unstructured(file_path)
        else:
            # Fallback to basic processing
            elements = self._process_fallback(file_path)
        
        # Associate captions with elements
        elements = self._associate_captions(elements)
        
        logger.info(f"Extracted {len(elements)} elements from {file_name}")
        
        return elements
    
    def _process_with_unstructured(self, file_path: str) -> List[MultimodalElement]:
        """
        Process PDF using unstructured library.
        
        Args:
            file_path: Path to PDF
            
        Returns:
            List of MultimodalElement objects
        """
        elements = []
        
        try:
            # Configure partitioning parameters
            params = {
                'filename': file_path,
                'strategy': self.strategy,
            }
            
            # Add optional parameters
            if self.extract_images:
                params['extract_images_in_pdf'] = True
            
            if self.infer_table_structure:
                params['infer_table_structure'] = True
            
            # Partition the PDF
            logger.info(f"Partitioning PDF with strategy: {self.strategy}")
            raw_elements = partition_pdf(**params)
            
            # Process each element
            for raw_el in raw_elements:
                element = self._convert_unstructured_element(raw_el, file_path)
                if element:
                    elements.append(element)
            
        except Exception as e:
            logger.error(f"Error processing with unstructured: {e}")
            # Fallback to basic processing
            elements = self._process_fallback(file_path)
        
        return elements
    
    def _convert_unstructured_element(
        self,
        raw_element: Any,
        source_file: str
    ) -> Optional[MultimodalElement]:
        """
        Convert an unstructured element to our MultimodalElement.
        
        Args:
            raw_element: Element from unstructured
            source_file: Source file name
            
        Returns:
            MultimodalElement or None
        """
        # Get page number
        page_number = getattr(raw_element.metadata, 'page_number', 1)
        
        # Get coordinates if available
        coordinates = None
        if hasattr(raw_element.metadata, 'coordinates'):
            coords = raw_element.metadata.coordinates
            if coords:
                coordinates = (
                    int(coords.get('x1', 0)),
                    int(coords.get('y1', 0)),
                    int(coords.get('x2', 0)),
                    int(coords.get('y2', 0))
                )
        
        # Get text content
        text_content = getattr(raw_element, 'text', '') or ''
        
        # Determine element type and create element
        element_type = ELEMENT_TYPE_TEXT
        content = text_content
        metadata = {}
        
        # Check element type
        if isinstance(raw_element, Table):
            element_type = ELEMENT_TYPE_TABLE
            # Try to get table as dict
            try:
                if hasattr(raw_element, 'to_dict'):
                    table_dict = raw_element.to_dict()
                    content = table_dict.get('text', text_content)
                    metadata['table_html'] = table_dict.get('html', '')
            except:
                content = text_content
            
        elif isinstance(raw_element, Image):
            element_type = ELEMENT_TYPE_IMAGE
            # Get image data if available
            if hasattr(raw_element.metadata, 'image_base64'):
                image_data = raw_element.metadata.image_base64
                if image_data:
                    # Decode base64 to bytes
                    try:
                        content = base64.b64decode(image_data)
                    except:
                        content = b''
            metadata['image_type'] = 'extracted'
            
            # Run OCR if enabled
            if self.ocr_images and PYTESSERACT_AVAILABLE and content:
                ocr_text = self._run_ocr(content)
                if ocr_text:
                    metadata['ocr_text'] = ocr_text
                    # Also create an OCR element
                    ocr_element = MultimodalElement(
                        element_id=self._generate_element_id(),
                        element_type=ELEMENT_TYPE_OCR,
                        content=ocr_text,
                        page_number=page_number,
                        coordinates=coordinates,
                        source_file=source_file,
                        caption=None,
                        metadata={'source_image_element': element_type}
                    )
                    # Return OCR element instead
                    return ocr_element
            
        elif isinstance(raw_element, Title):
            element_type = ELEMENT_TYPE_TITLE
            
        elif isinstance(raw_element, Header):
            element_type = ELEMENT_TYPE_HEADER
            
        elif isinstance(raw_element, Footer):
            element_type = ELEMENT_TYPE_FOOTER
        
        # Get caption if available
        caption = getattr(raw_element.metadata, 'caption', None)
        
        # Create element
        element = MultimodalElement(
            element_id=self._generate_element_id(),
            element_type=element_type,
            content=content,
            page_number=page_number,
            coordinates=coordinates,
            source_file=source_file,
            caption=caption,
            metadata=metadata
        )
        
        return element
    
    def _run_ocr(self, image_data: bytes) -> str:
        """
        Run OCR on image data.
        
        Args:
            image_data: Image bytes
            
        Returns:
            Extracted text or empty string
        """
        if not PYTESSERACT_AVAILABLE:
            return ""
        
        try:
            # Load image from bytes
            image = PILImage.open(io.BytesIO(image_data))
            
            # Run OCR
            text = pytesseract.image_to_string(image)
            
            return text.strip()
            
        except Exception as e:
            logger.warning(f"OCR failed: {e}")
            return ""
    
    def _process_fallback(self, file_path: str) -> List[MultimodalElement]:
        """
        Fallback processing using basic pypdf.
        
        Args:
            file_path: Path to PDF
            
        Returns:
            List of MultimodalElement objects
        """
        elements = []
        
        if not PYPDF_AVAILABLE:
            logger.error("pypdf not available for fallback processing")
            return elements
        
        try:
            reader = PdfReader(file_path)
            file_name = os.path.basename(file_path)
            
            for page_num, page in enumerate(reader.pages, 1):
                # Extract text
                text = page.extract_text()
                
                if text:
                    element = MultimodalElement(
                        element_id=self._generate_element_id(),
                        element_type=ELEMENT_TYPE_TEXT,
                        content=text,
                        page_number=page_num,
                        source_file=file_name,
                        metadata={'extraction_method': 'pypdf'}
                    )
                    elements.append(element)
        
        except Exception as e:
            logger.error(f"Fallback processing failed: {e}")
        
        return elements
    
    def _associate_captions(
        self,
        elements: List[MultimodalElement]
    ) -> List[MultimodalElement]:
        """
        Associate captions with their respective elements.
        
        This method looks for caption elements near other elements
        and associates them based on proximity.
        
        Args:
            elements: List of extracted elements
            
        Returns:
            Elements with captions associated
        """
        # Find caption elements
        captions = []
        other_elements = []
        
        for el in elements:
            if el.caption:
                captions.append(el)
            else:
                other_elements.append(el)
        
        # Simple caption association based on position
        # In a real implementation, this would use more sophisticated logic
        for caption in captions:
            # Find nearest element on same page
            best_match = None
            best_distance = float('inf')
            
            for el in other_elements:
                if el.page_number == caption.page_number:
                    # Simple distance metric
                    if caption.coordinates != (0, 0, 0, 0):
                        distance = abs(el.coordinates[1] - caption.coordinates[3])
                    else:
                        distance = float('inf')
                    
                    if distance < best_distance:
                        best_distance = distance
                        best_match = el
            
            # Associate caption if close enough
            if best_match and best_distance < 500:  # Threshold
                best_match.caption = caption.content
                # Remove caption from elements (it's now associated)
                if caption in elements:
                    elements.remove(caption)
        
        return elements
    
    def extract_tables(self, elements: List[MultimodalElement]) -> List[TableData]:
        """
        Extract table data from elements.
        
        Args:
            elements: List of MultimodalElement objects
            
        Returns:
            List of TableData objects
        """
        tables = []
        
        for el in elements:
            if el.element_type == ELEMENT_TYPE_TABLE:
                table = TableData(
                    table_id=el.element_id,
                    page_number=el.page_number,
                    caption=el.caption
                )
                
                # Try to parse table content
                if isinstance(el.content, dict):
                    table.headers = el.content.get('columns', [])
                    table.rows = el.content.get('rows', [])
                elif isinstance(el.content, str):
                    # Try to parse as simple table
                    lines = el.content.strip().split('\n')
                    if lines:
                        table.headers = lines[0].split('|')
                        table.rows = [line.split('|') for line in lines[1:]]
                
                tables.append(table)
        
        return tables
    
    def get_elements_by_type(
        self,
        elements: List[MultimodalElement],
        element_type: str
    ) -> List[MultimodalElement]:
        """
        Filter elements by type.
        
        Args:
            elements: List of elements
            element_type: Type to filter by
            
        Returns:
            Filtered list of elements
        """
        return [el for el in elements if el.element_type == element_type]
    
    def get_elements_by_page(
        self,
        elements: List[MultimodalElement],
        page_number: int
    ) -> List[MultimodalElement]:
        """
        Get elements from a specific page.
        
        Args:
            elements: List of elements
            page_number: Page number to filter by
            
        Returns:
            Elements from that page
        """
        return [el for el in elements if el.page_number == page_number]
    
    def get_statistics(self, elements: List[MultimodalElement]) -> Dict:
        """
        Get statistics about extracted elements.
        
        Args:
            elements: List of elements
            
        Returns:
            Dictionary of statistics
        """
        stats = {
            'total_elements': len(elements),
            'by_type': {},
            'by_page': {},
            'with_captions': 0
        }
        
        # Count by type
        for el in elements:
            stats['by_type'][el.element_type] = stats['by_type'].get(el.element_type, 0) + 1
            
            # Count by page
            stats['by_page'][el.page_number] = stats['by_page'].get(el.page_number, 0) + 1
            
            # Count with captions
            if el.caption:
                stats['with_captions'] += 1
        
        return stats


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def process_multimodal_pdf(
    file_path: str,
    **kwargs
) -> List[MultimodalElement]:
    """
    Convenience function to process a PDF.
    
    Args:
        file_path: Path to PDF
        **kwargs: Additional arguments for processor
        
    Returns:
        List of MultimodalElement objects
    """
    processor = MultimodalDocumentProcessor(**kwargs)
    return processor.process_pdf(file_path)


def extract_all_content(
    file_path: str,
    include_images: bool = True,
    include_tables: bool = True,
    include_ocr: bool = True
) -> Dict[str, Any]:
    """
    Extract all content from a PDF file.
    
    This is a comprehensive function that extracts:
    - Text elements
    - Table data
    - Image metadata
    - OCR text
    - Statistics
    
    Args:
        file_path: Path to PDF
        include_images: Whether to extract images
        include_tables: Whether to extract tables
        include_ocr: Whether to run OCR
        
    Returns:
        Dictionary with all extracted content
    """
    processor = MultimodalDocumentProcessor(
        extract_images=include_images,
        extract_tables=include_tables,
        ocr_images=include_ocr
    )
    
    # Process PDF
    elements = processor.process_pdf(file_path)
    
    # Extract tables
    tables = processor.extract_tables(elements)
    
    # Get statistics
    stats = processor.get_statistics(elements)
    
    # Convert to LangChain documents
    documents = [el.to_langchain_document() for el in elements]
    
    return {
        'elements': elements,
        'tables': tables,
        'documents': documents,
        'statistics': stats,
        'file_name': os.path.basename(file_path)
    }


# ============================================================================
# MAIN EXECUTION (FOR TESTING)
# ============================================================================

if __name__ == "__main__":
    """
    Main execution block for testing.
    """
    print("=" * 60)
    print("Multimodal Document Processor - Test")
    print("=" * 60)
    
    # Check dependencies
    print("\nDependency Status:")
    print(f"  unstructured: {UNSTRUCTURED_AVAILABLE}")
    print(f"  pypdf: {PYPDF_AVAILABLE}")
    print(f"  pytesseract: {PYTESSERACT_AVAILABLE}")
    print(f"  Pillow: {PIL_AVAILABLE}")
    
    # Note about usage
    print("\nTo use this processor:")
    print("  from multimodal_processor import process_multimodal_pdf")
    print("  elements = process_multimodal_pdf('your_file.pdf')")
    
    print("\n" + "=" * 60)
    print("Processor module ready.")
    print("=" * 60)
