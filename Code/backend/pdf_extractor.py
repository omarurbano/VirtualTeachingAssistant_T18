"""
PDF Multimodal Extractor using PyMuPDF (fitz)
Extracts text, images, and tables with precise bounding boxes and metadata.

Author: CPT_S 421 Development Team
Version: 1.0.0
Created: 2025-03-10
"""

import fitz  # PyMuPDF
from typing import List, Dict, Any, Tuple
import os
import logging

logger = logging.getLogger(__name__)

# ============================================================================
# DATA CLASSES
# ============================================================================

class TextBlock:
    """A contiguous text region with bounding box."""

    def __init__(self, text: str, bbox: Tuple[float, float, float, float],
                 block_type: str = 'text'):
        self.text = text.strip()
        self.bbox = bbox  # (x0, y0, x1, y1)
        self.block_type = block_type  # 'text', 'header', 'footer', 'caption'
        self.block_id = None  # Will be set by parent

    def to_dict(self) -> Dict:
        return {
            'text': self.text,
            'bbox': self.bbox,
            'block_type': self.block_type,
            'block_id': self.block_id
        }


class PDFImage:
    """An extracted image with metadata."""

    def __init__(self, image_bytes: bytes, bbox: Tuple[float, float, float, float],
                 page_number: int, image_index: int):
        self.image_bytes = image_bytes
        self.bbox = bbox
        self.page_number = page_number
        self.image_index = image_index
        self.element_id = f"img_p{page_number}_{image_index:04d}"
        self.caption = None  # To be filled by BLIP-2
        self.ocr_text = None  # To be filled by OCR
        self.width = bbox[2] - bbox[0] if bbox else 0
        self.height = bbox[3] - bbox[1] if bbox else 0

    def to_dict(self) -> Dict:
        return {
            'element_id': self.element_id,
            'page_number': self.page_number,
            'bbox': self.bbox,
            'width': self.width,
            'height': self.height,
            'caption': self.caption,
            'ocr_text': self.ocr_text,
            'has_caption': self.caption is not None and len(self.caption) > 0,
            'has_ocr': self.ocr_text is not None and len(self.ocr_text.strip()) > 0
        }


class PDFTable:
    """A table extracted from PDF."""

    def __init__(self, table_data: List[List], bbox: Tuple[float, float, float, float],
                 page_number: int, table_index: int):
        self.table_data = table_data  # 2D list of cells
        self.bbox = bbox
        self.page_number = page_number
        self.table_index = table_index
        self.element_id = f"tbl_p{page_number}_{table_index:04d}"
        self.markdown = None  # Will be converted
        self.headers = []
        self.row_count = len(table_data)
        self.col_count = len(table_data[0]) if table_data else 0

    def to_markdown(self) -> str:
        """Convert table data to Markdown format."""
        if not self.table_data:
            return ""

        lines = []
        # Header row
        if self.headers:
            lines.append("| " + " | ".join(self.headers) + " |")
            lines.append("| " + " | ".join(["---"] * len(self.headers)) + " |")
        else:
            # Use first row as header if not specified
            lines.append("| " + " | ".join(self.table_data[0]) + " |")
            lines.append("| " + " | ".join(["---"] * len(self.table_data[0])) + " |")
            start_idx = 1
        # Data rows
        start_idx = 1 if self.headers else 0
        for row in self.table_data[start_idx:]:
            lines.append("| " + " | ".join(str(cell) for cell in row) + " |")

        return "\n".join(lines)

    def to_dict(self) -> Dict:
        return {
            'element_id': self.element_id,
            'page_number': self.page_number,
            'bbox': self.bbox,
            'row_count': self.row_count,
            'col_count': self.col_count,
            'markdown': self.to_markdown(),
            'raw_data': self.table_data,
            'headers': self.headers
        }


class PDFPage:
    """Represents a single PDF page with all its elements."""

    def __init__(self, page_number: int, page_obj, page_size: Tuple[float, float]):
        self.page_number = page_number
        self.page_obj = page_obj
        self.page_size = page_size  # (width, height)
        self.text_blocks: List[TextBlock] = []
        self.images: List[PDFImage] = []
        self.tables: List[PDFTable] = []

    def to_dict(self) -> Dict:
        return {
            'page_number': self.page_number,
            'page_size': self.page_size,
            'text_blocks': [tb.to_dict() for tb in self.text_blocks],
            'images': [img.to_dict() for img in self.images],
            'tables': [tbl.to_dict() for tbl in self.tables],
            'stats': {
                'text_blocks': len(self.text_blocks),
                'images': len(self.images),
                'tables': len(self.tables)
            }
        }


# ============================================================================
# MAIN EXTRACTOR CLASS
# ============================================================================

class PyMuPDFExtractor:
    """
    Extracts all multimodal elements from a PDF using PyMuPDF (fitz).

    Features:
    - Text extraction with bounding boxes and type classification
    - Image extraction as PNG bytes with precise positioning
    - Table detection via layout analysis (basic heuristic)
    - Page-level organization and metadata
    """

    def __init__(self, extract_images: bool = True, extract_tables: bool = True,
                 min_image_size: int = 100):
        """
        Initialize the extractor.

        Args:
            extract_images: Whether to extract images
            extract_tables: Whether to attempt table extraction
            min_image_size: Minimum width/height in pixels to consider an image
        """
        self.extract_images = extract_images
        self.extract_tables = extract_tables
        self.min_image_size = min_image_size

    def extract(self, pdf_path: str) -> Dict[int, PDFPage]:
        """
        Main extraction method.

        Args:
            pdf_path: Path to PDF file

        Returns:
            Dict mapping page_number -> PDFPage object with all elements

        Raises:
            FileNotFoundError: If PDF doesn't exist
            ValueError: If PDF can't be opened
        """
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        try:
            doc = fitz.open(pdf_path)
        except Exception as e:
            raise ValueError(f"Failed to open PDF: {e}")

        pages = {}
        logger.info(f"Extracting from PDF: {pdf_path} ({len(doc)} pages)")

        for page_num in range(len(doc)):
            page = doc[page_num]
            page_number = page_num + 1  # 1-indexed
            page_size = (page.rect.width, page.rect.height)

            pdf_page = PDFPage(page_number, page, page_size)

            # 1. Extract text blocks
            text_blocks = self._extract_text_blocks(page, page_number)
            pdf_page.text_blocks = text_blocks

            # 2. Extract images
            if self.extract_images:
                images = self._extract_images(page, page_number)
                pdf_page.images = images

            # 3. Extract tables
            if self.extract_tables:
                tables = self._extract_tables(page, page_number, text_blocks)
                pdf_page.tables = tables

            pages[page_number] = pdf_page

            logger.debug(f"Page {page_number}: {len(text_blocks)} text, "
                         f"{len(images)} images, {len(tables)} tables")

        doc.close()
        logger.info(f"Extraction complete: {len(pages)} pages processed")
        return pages

    def _extract_text_blocks(self, page, page_number: int) -> List[TextBlock]:
        """
        Extract text blocks with bounding boxes using PyMuPDF's text dict.

        Returns list of TextBlock objects sorted by position (top to bottom).
        """
        blocks = []

        try:
            # Get structured text data
            text_dict = page.get_text("dict")

            for block_idx, block in enumerate(text_dict["blocks"]):
                # block_type: 0=text, 1=image, 2=formula, 3=...
                if block["type"] == 0:  # Text block
                    # Extract text from lines and spans
                    lines = []
                    for line in block["lines"]:
                        for span in line["spans"]:
                            lines.append(span["text"])
                    text = " ".join(lines).strip()

                    if text and len(text) > 0:
                        bbox = block["bbox"]  # (x0, y0, x1, y1)
                        block_obj = TextBlock(text, bbox)

                        # Try to determine block type based on font size
                        # (larger fonts likely headers)
                        if len(block["lines"]) > 0:
                            avg_font_size = sum(
                                span["size"] for line in block["lines"] for span in line["spans"]
                            ) / sum(len(line["spans"]) for line in block["lines"])
                            if avg_font_size > 14:
                                block_obj.block_type = 'header'
                            elif avg_font_size < 8:
                                block_obj.block_type = 'caption'
                            else:
                                block_obj.block_type = 'text'

                        block_obj.block_id = f"blk_p{page_number}_{block_idx:04d}"
                        blocks.append(block_obj)

        except Exception as e:
            logger.warning(f"Error extracting text blocks on page {page_number}: {e}")

        # Sort blocks by vertical position (top to bottom)
        blocks.sort(key=lambda b: b.bbox[1])

        return blocks

    def _extract_images(self, page, page_number: int) -> List[PDFImage]:
        """
        Extract images from page as PNG bytes.

        Returns list of PDFImage objects.
        """
        images = []

        if not self.extract_images:
            return images

        try:
            # Get image list from page
            image_list = page.get_images(full=True)  # List of tuples

            for img_idx, img_info in enumerate(image_list):
                xref = img_info[0]  # XRef number

                try:
                    # Extract image as pixmap
                    pix = fitz.Pixmap(page.parent, xref)

                    # Convert to RGB if necessary (handles CMYK, grayscale)
                    if pix.n > 4:  # CMYK has 4 channels, but >4 indicates unusual format
                        pix = fitz.Pixmap(fitz.csRGB, pix)

                    # Check image size
                    if pix.width < self.min_image_size or pix.height < self.min_image_size:
                        logger.debug(f"Skipping small image {xref}: {pix.width}x{pix.height}")
                        pix = None
                        continue

                    # Convert to PNG bytes
                    image_bytes = pix.tobytes("png")

                    # Find bounding box for this image
                    bbox = self._find_image_bbox(page, xref)

                    img_obj = PDFImage(
                        image_bytes=image_bytes,
                        bbox=bbox,
                        page_number=page_number,
                        image_index=img_idx
                    )
                    images.append(img_obj)

                    # Free pixmap memory
                    pix = None

                except Exception as e:
                    logger.warning(f"Failed to extract image {xref} on page {page_number}: {e}")
                    continue

        except Exception as e:
            logger.warning(f"Error getting image list on page {page_number}: {e}")

        return images

    def _find_image_bbox(self, page, xref: int) -> Tuple[float, float, float, float]:
        """
        Find the bounding box of an image on the page.

        Searches through page's drawing objects to find the image's position.
        """
        try:
            # Get all drawings/forms on page
            drawings = page.get_drawings()

            for drawing in drawings:
                # Check if this drawing references our xref
                if drawing.get('xref') == xref:
                    rect = drawing['rect']  # fitz.Rect
                    return (rect.x0, rect.y0, rect.x1, rect.y1)

            # Alternative: search through page.get_text("rawdict") for image blocks
            text_dict = page.get_text("rawdict")
            for block in text_dict["blocks"]:
                if block.get("type") == 1:  # Image block
                    if block.get("number") == xref:
                        return block["bbox"]

        except Exception as e:
            logger.debug(f"Could not find bbox for image {xref}: {e}")

        # Fallback: return entire page bounds
        return (0, 0, page.rect.width, page.rect.height)

    def _extract_tables(self, page, page_number: int, text_blocks: List[TextBlock]) -> List[PDFTable]:
        """
        Extract tables using heuristic layout analysis.

        This is a basic implementation. For production, consider:
        - camelot-py[cv] for lattice tables
        - tabula-py for stream tables
        - unstructured's table extraction

        Args:
            page: fitz.Page object
            page_number: Current page number
            text_blocks: Already extracted text blocks

        Returns:
            List of PDFTable objects
        """
        tables = []

        if not self.extract_tables or not text_blocks:
            return tables

        try:
            # Strategy: Group text blocks into rows by Y coordinate
            # Then identify rows with multiple columns as potential table rows

            # Group blocks by line (snap Y to grid)
            lines = {}
            for block in text_blocks:
                # Use midpoint Y, snapped to 5-point grid for tolerance
                y_mid = (block.bbox[1] + block.bbox[3]) / 2
                line_key = round(y_mid / 5) * 5  # Snap to 5pt grid

                if line_key not in lines:
                    lines[line_key] = []
                lines[line_key].append(block)

            # Sort lines by Y position
            sorted_line_keys = sorted(lines.keys())

            # Find consecutive lines with multiple blocks (table candidates)
            table_candidate_lines = []
            current_table = []

            for y_key in sorted_line_keys:
                blocks = lines[y_key]
                # Sort blocks in this line by X position
                blocks.sort(key=lambda b: b.bbox[0])

                # If this line has 2+ blocks, it's potentially a table row
                if len(blocks) >= 2:
                    current_table.append(blocks)
                else:
                    # End of table candidate
                    if len(current_table) >= 2:  # At least 2 rows
                        tables.append(current_table)
                    current_table = []

            # Check last table
            if len(current_table) >= 2:
                tables.append(current_table)

            # Convert table candidates to PDFTable objects
            pdf_tables = []
            for table_idx, table_rows in enumerate(tables):
                # Extract text from each cell
                table_data = []
                for row_blocks in table_rows:
                    row_text = [block.text for block in row_blocks]
                    table_data.append(row_text)

                if not table_data:
                    continue

                # Calculate bounding box covering all rows
                all_bboxes = [block.bbox for row in table_rows for block in row]
                x0 = min(b[0] for b in all_bboxes)
                y0 = min(b[1] for b in all_bboxes)
                x1 = max(b[2] for b in all_bboxes)
                y1 = max(b[3] for b in all_bboxes)

                pdf_table = PDFTable(
                    table_data=table_data,
                    bbox=(x0, y0, x1, y1),
                    page_number=page_number,
                    table_index=table_idx
                )

                # Try to detect headers (first row with different formatting)
                if len(table_data) > 1:
                    first_row = table_data[0]
                    second_row = table_data[1]
                    # If first row has shorter/uppercase text, likely headers
                    if all(len(cell) < 50 for cell in first_row):
                        pdf_table.headers = first_row

                pdf_tables.append(pdf_table)

                logger.debug(f"Detected table on page {page_number}: "
                             f"{len(table_data)} rows x {len(table_data[0])} cols")

        except Exception as e:
            logger.warning(f"Error extracting tables on page {page_number}: {e}")

        return pdf_tables

    def save_image_to_file(self, image: PDFImage, output_dir: str) -> str:
        """
        Save extracted image to disk.

        Args:
            image: PDFImage object
            output_dir: Directory to save to

        Returns:
            Path to saved image file
        """
        os.makedirs(output_dir, exist_ok=True)

        filename = f"{image.element_id}.png"
        filepath = os.path.join(output_dir, filename)

        try:
            with open(filepath, 'wb') as f:
                f.write(image.image_bytes)
            return filepath
        except Exception as e:
            logger.error(f"Failed to save image {image.element_id}: {e}")
            return None


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def extract_pdf_multimodal(pdf_path: str, output_dir: str = None,
                          extract_images: bool = True,
                          extract_tables: bool = True) -> Dict[int, PDFPage]:
    """
    Convenience function to extract all content from a PDF.

    Args:
        pdf_path: Path to PDF file
        output_dir: If provided, save extracted images to this directory
        extract_images: Whether to extract images
        extract_tables: Whether to extract tables

    Returns:
        Dict of PDFPage objects keyed by page number
    """
    extractor = PyMuPDFExtractor(
        extract_images=extract_images,
        extract_tables=extract_tables
    )

    pages = extractor.extract(pdf_path)

    # Save images if output_dir provided
    if output_dir and extract_images:
        for page in pages.values():
            for image in page.images:
                filepath = extractor.save_image_to_file(image, output_dir)
                if filepath:
                    # Store relative path in image metadata
                    image.saved_path = filepath

    return pages


def get_pdf_metadata(pages: Dict[int, PDFPage]) -> Dict[str, Any]:
    """
    Generate summary statistics for extracted PDF content.

    Args:
        pages: Dict from extract()

    Returns:
        Dict with counts and metadata
    """
    total_text_blocks = 0
    total_images = 0
    total_tables = 0
    total_text_chars = 0

    for page in pages.values():
        total_text_blocks += len(page.text_blocks)
        total_images += len(page.images)
        total_tables += len(page.tables)

        for block in page.text_blocks:
            total_text_chars += len(block.text)

    return {
        'total_pages': len(pages),
        'total_text_blocks': total_text_blocks,
        'total_images': total_images,
        'total_tables': total_tables,
        'total_text_chars': total_text_chars,
        'pages': {pnum: page.to_dict() for pnum, page in pages.items()}
    }
