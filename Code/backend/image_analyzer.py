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
from typing import Dict, Any, Optional, List, Union
from PIL import Image

logger = logging.getLogger(__name__)

# Check for optional dependencies
try:
    import torch
    from transformers import pipeline
    VISION_AVAILABLE = True
except ImportError:
    VISION_AVAILABLE = False
    logger.warning("Transformers not available. Install: pip install transformers torch")

try:
    import pytesseract
    # Configure Tesseract executable path for Windows
    import os
    tesseract_path = r"C:\Users\nsudi\OneDrive\Documents\Tesseract\tesseract.exe"
    if os.path.exists(tesseract_path):
        pytesseract.pytesseract.tesseract_cmd = tesseract_path
    # Verify the tesseract binary is actually reachable before marking available
    pytesseract.get_tesseract_version()
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False
    logger.warning("pytesseract not available. Install: pip install pytesseract")
except Exception:
    TESSERACT_AVAILABLE = False
    logger.warning("Tesseract binary not found. OCR will be skipped. Install tesseract-ocr and ensure it is on PATH.")


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
        },
        'git-base': {
            'name': 'microsoft/git-base',
            'size_gb': 1.5,
            'description': 'Microsoft GIT-base (alternative to BLIP-2)'
        },
        'git-small': {
            'name': 'microsoft/git-small',
            'size_gb': 0.5,
            'description': 'Microsoft GIT-small (faster, less accurate)'
        }
    }

    def __init__(self, model_name: str = 'git-base', device: str = None, timeout: int = 30):
        """
        Initialize image analyzer.

        Args:
            model_name: Model variant (key from BLIP2_MODELS)
            device: 'cuda', 'cpu', or None for auto-detect
            timeout: Timeout for caption generation in seconds
        """
        self.model_name = model_name
        self.device = device or self._detect_device()
        self.timeout = timeout
        self.blip_processor = None
        self.blip_model = None
        self.load_error = None

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
        """Load vision model (BLIP-2 or Microsoft GIT) and processor."""
        if not VISION_AVAILABLE:
            logger.warning("Transformers not available")
            self.load_error = "Transformers not installed"
            return

        model_key = self.model_name
        if model_key not in self.BLIP2_MODELS:
            logger.warning(f"Unknown model: {model_key}. Using default: git-base")
            model_key = 'git-base'

        model_path = self.BLIP2_MODELS[model_key]['name']
        logger.info(f"Loading vision model: {model_path} on {self.device}")

        try:
            # Use pipeline for image-to-text
            from transformers import pipeline
            
            self.caption_pipeline = pipeline(
                'image-text-to-text',
                model=model_path,
                device='cpu'
            )
            logger.info(f"Vision model loaded successfully on {self.device}")

        except Exception as e:
            logger.error(f"Failed to load vision model: {e}")
            self.caption_pipeline = None
            self.load_error = str(e)

    def generate_caption(self, image_bytes: bytes, prompt: str = None) -> str:
        """
        Generate a descriptive caption for an image.

        Args:
            image_bytes: PNG/JPEG image data
            prompt: Optional prompt to guide captioning

        Returns:
            Caption string (empty if failed)
        """
        if not self.caption_pipeline:
            return ""

        try:
            # Load image
            image = Image.open(io.BytesIO(image_bytes)).convert('RGB')

            # Default prompt if not provided
            text_prompt = prompt if prompt else "a photo showing"

            # Generate caption using pipeline
            result = self.caption_pipeline(image, text=text_prompt, max_length=100)
            
            if result and len(result) > 0:
                # Extract generated text from result
                generated = result[0].get('generated_text', '')
                # Remove the prompt prefix if present
                if generated.startswith(text_prompt):
                    generated = generated[len(text_prompt):].strip()
                return generated
            return ""

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
        if self.caption_pipeline:
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

def create_image_analyzer(model_name: str = None, device: str = None, timeout: int = 30) -> Any:
    """
    Factory function to create appropriate image analyzer.
    
    Args:
        model_name: Vision model variant (None uses default: git-base)
        device: Device to use (None for auto-detect)
        timeout: Timeout for inference in seconds

    Returns:
        ImageAnalyzer or SimpleImageAnalyzer instance
    """
    import os
    
    # Check environment flags
    skip_vision = os.environ.get('SKIP_BLIP2', '').lower() == 'true'
    
    # Try vision model first if not skipped
    if VISION_AVAILABLE and not skip_vision:
        model = model_name or 'git-base'
        try:
            logger.info(f"Attempting to load vision model: {model}")
            analyzer = ImageAnalyzer(model_name=model, device=device, timeout=timeout)
            if analyzer.caption_pipeline is not None:
                logger.info(f"Vision model {model} loaded successfully!")
                return analyzer
            else:
                logger.warning(f"Vision model {model} loaded but pipeline is None, falling back to OCR")
        except Exception as e:
            logger.warning(f"Failed to load vision model {model}: {e}, falling back to OCR")
    
    # Default to SimpleImageAnalyzer (OCR only)
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
