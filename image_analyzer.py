"""
Image Analysis using BLIP-2 for captioning and pytesseract for OCR.

Provides multimodal understanding of images:
- BLIP-2 generates descriptive captions
- pytesseract extracts embedded text
- Combined analysis for rich metadata

Author: CPT_S 421 Development Team
Version: 1.0.0
Created: 2025-03-10
"""

import io
import logging
from typing import Dict, Any, Optional, List
from PIL import Image

logger = logging.getLogger(__name__)

# Check for optional dependencies
try:
    import torch
    from transformers import Blip2Processor, Blip2ForConditionalGeneration
    BLIP2_AVAILABLE = True
except ImportError:
    BLIP2_AVAILABLE = False
    logger.warning("BLIP-2 not available. Install: pip install transformers torch")

try:
    import pytesseract
    # Configure Tesseract executable path for Windows
    import os
    tesseract_path = r"C:\Users\nsudi\OneDrive\Documents\Tesseract\tesseract.exe"
    if os.path.exists(tesseract_path):
        pytesseract.pytesseract.tesseract_cmd = tesseract_path
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False
    logger.warning("pytesseract not available. Install: pip install pytesseract")


class ImageAnalyzer:
    """
    Analyzes images using BLIP-2 for captioning and pytesseract for OCR.

    Features:
    - Generate natural language descriptions of image content
    - Extract text embedded in images (e.g., charts, signs)
    - Combined analysis for comprehensive understanding
    - Graceful fallback when models unavailable
    """

    # BLIP-2 model options
    BLIP2_MODELS = {
        'blip2-opt-2.7b': {
            'name': 'Salesforce/blip2-opt-2.7b',
            'size_gb': 15.5,
            'description': 'Full-size BLIP-2 with OPT-2.7B decoder (best quality)'
        },
        'blip2-flan-t5-xl': {
            'name': 'Salesforce/blip2-flan-t5-xl',
            'size_gb': 5.0,
            'description': 'Smaller BLIP-2 with Flan-T5-XL (good balance)'
        },
        'blip2-flan-t5-xxl': {
            'name': 'Salesforce/blip2-flan-t5-xxl',
            'size_gb': 15.0,
            'description': 'Largest BLIP-2 with Flan-T5-XXL (highest quality)'
        }
    }

    def __init__(self, model_name: str = 'blip2-flan-t5-xl', device: str = None):
        """
        Initialize image analyzer.

        Args:
            model_name: BLIP-2 model variant (key from BLIP2_MODELS)
            device: 'cuda', 'cpu', or None for auto-detect
        """
        self.model_name = model_name
        self.device = device or self._detect_device()
        self.blip_processor = None
        self.blip_model = None

        self._load_blip2()

    def _detect_device(self) -> str:
        """Auto-detect best available device."""
        if torch.cuda.is_available():
            return 'cuda'
        elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
            return 'mps'
        else:
            return 'cpu'

    def _load_blip2(self):
        """Load BLIP-2 model and processor."""
        if not BLIP2_AVAILABLE:
            logger.warning("BLIP-2 dependencies not installed")
            return

        model_key = self.model_name
        if model_key not in self.BLIP2_MODELS:
            logger.warning(f"Unknown model: {model_key}. Using default: blip2-flan-t5-xl")
            model_key = 'blip2-flan-t5-xl'

        model_path = self.BLIP2_MODELS[model_key]['name']
        logger.info(f"Loading BLIP-2: {model_path} on {self.device}")

        try:
            # Load processor
            self.blip_processor = Blip2Processor.from_pretrained(model_path)

            # Load model with appropriate dtype
            torch_dtype = torch.float16 if self.device == 'cuda' else torch.float32
            self.blip_model = Blip2ForConditionalGeneration.from_pretrained(
                model_path,
                torch_dtype=torch_dtype
            ).to(self.device)

            logger.info(f"BLIP-2 loaded successfully on {self.device}")

        except Exception as e:
            logger.error(f"Failed to load BLIP-2: {e}")
            self.blip_model = None
            self.blip_processor = None

    def generate_caption(self, image_bytes: bytes, prompt: str = None) -> str:
        """
        Generate a descriptive caption for an image.

        Args:
            image_bytes: PNG/JPEG image data
            prompt: Optional prompt to guide captioning (e.g., "Describe this image in detail")

        Returns:
            Caption string (empty if failed)
        """
        if not self.blip_model or not self.blip_processor:
            return ""

        try:
            # Load image
            image = Image.open(io.BytesIO(image_bytes)).convert('RGB')

            # Prepare inputs
            if prompt:
                inputs = self.blip_processor(image, text=prompt, return_tensors="pt").to(self.device)
            else:
                inputs = self.blip_processor(image, return_tensors="pt").to(self.device)

            # Generate caption
            with torch.no_grad():
                generated_ids = self.blip_model.generate(**inputs, max_new_tokens=100)
                caption = self.blip_processor.batch_decode(
                    generated_ids, skip_special_tokens=True
                )[0]

            return caption.strip()

        except Exception as e:
            logger.warning(f"Caption generation failed: {e}")
            return ""

    def extract_ocr(self, image_bytes: bytes, lang: str = 'eng') -> str:
        """
        Extract text from image using OCR.

        Args:
            image_bytes: PNG/JPEG image data
            lang: Language code for OCR (default: 'eng')

        Returns:
            Extracted text string (empty if failed or no text)
        """
        if not TESSERACT_AVAILABLE:
            return ""

        try:
            # Load image with PIL
            image = Image.open(io.BytesIO(image_bytes))

            # Convert to RGB if needed (handles RGBA, grayscale)
            if image.mode != 'RGB':
                image = image.convert('RGB')

            # Run OCR
            ocr_text = pytesseract.image_to_string(image, lang=lang)

            return ocr_text.strip()

        except Exception as e:
            logger.warning(f"OCR failed: {e}")
            return ""

    def analyze(self, image_bytes: bytes, caption_prompt: str = None) -> Dict[str, Any]:
        """
        Comprehensive image analysis.

        Args:
            image_bytes: PNG/JPEG image data
            caption_prompt: Optional custom prompt for captioning

        Returns:
            Dict with keys:
                - caption: str (BLIP-2 description)
                - ocr_text: str (extracted text)
                - has_text: bool (whether OCR found text)
                - caption_success: bool
                - ocr_success: bool
        """
        result = {
            'caption': '',
            'ocr_text': '',
            'has_text': False,
            'caption_success': False,
            'ocr_success': False
        }

        # Generate caption
        if self.blip_model:
            caption = self.generate_caption(image_bytes, caption_prompt)
            result['caption'] = caption
            result['caption_success'] = len(caption) > 0
        else:
            result['caption'] = "[Captioning model not available]"

        # Extract OCR
        if TESSERACT_AVAILABLE:
            ocr_text = self.extract_ocr(image_bytes)
            result['ocr_text'] = ocr_text
            result['ocr_success'] = len(ocr_text.strip()) > 0
            result['has_text'] = result['ocr_success']
        else:
            result['ocr_text'] = "[OCR not available]"

        return result


class SimpleImageAnalyzer:
    """
    Fallback image analyzer when BLIP-2 is not available.

    Uses only OCR to extract text from images.
    """

    def __init__(self):
        self.available = TESSERACT_AVAILABLE

    def analyze(self, image_bytes: bytes) -> Dict[str, Any]:
        """Analyze image with OCR only."""
        result = {
            'caption': '',
            'ocr_text': '',
            'has_text': False,
            'caption_success': False,
            'ocr_success': False
        }

        if self.available:
            try:
                import pytesseract
                from PIL import Image

                image = Image.open(io.BytesIO(image_bytes))
                if image.mode != 'RGB':
                    image = image.convert('RGB')

                ocr_text = pytesseract.image_to_string(image)
                result['ocr_text'] = ocr_text.strip()
                result['ocr_success'] = len(result['ocr_text']) > 0
                result['has_text'] = result['ocr_success']
            except Exception as e:
                logger.warning(f"Simple OCR failed: {e}")

        return result


# ============================================================================
# FACTORY FUNCTION
# ============================================================================

def create_image_analyzer(model_name: str = None, device: str = None) -> ImageAnalyzer:
    """
    Factory function to create appropriate image analyzer.

    Args:
        model_name: BLIP-2 model variant (None for auto-select)
        device: Device to use (None for auto-detect)

    Returns:
        ImageAnalyzer or SimpleImageAnalyzer instance
    """
    if BLIP2_AVAILABLE:
        model = model_name or 'blip2-flan-t5-xl'
        return ImageAnalyzer(model_name=model, device=device)
    else:
        logger.info("Using SimpleImageAnalyzer (OCR only)")
        return SimpleImageAnalyzer()


# ============================================================================
# BATCH PROCESSING
# ============================================================================

def analyze_images_batch(images: List[Dict], analyzer=None, batch_size: int = 4) -> Dict[str, Dict]:
    """
    Analyze multiple images efficiently.

    Args:
        images: List of dicts with keys: 'image_bytes', 'element_id'
        analyzer: ImageAnalyzer instance (created if None)
        batch_size: Process images in batches for GPU memory

    Returns:
        Dict mapping element_id -> analysis result
    """
    if analyzer is None:
        analyzer = create_image_analyzer()

    results = {}

    # Process in batches
    for i in range(0, len(images), batch_size):
        batch = images[i:i+batch_size]

        for img_data in batch:
            element_id = img_data['element_id']
            image_bytes = img_data['image_bytes']

            try:
                analysis = analyzer.analyze(image_bytes)
                results[element_id] = analysis
            except Exception as e:
                logger.error(f"Failed to analyze image {element_id}: {e}")
                results[element_id] = {
                    'caption': '',
                    'ocr_text': '',
                    'has_text': False,
                    'caption_success': False,
                    'ocr_success': False,
                    'error': str(e)
                }

    return results
