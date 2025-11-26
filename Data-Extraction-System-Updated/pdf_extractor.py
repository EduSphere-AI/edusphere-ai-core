#!/usr/bin/env python3
"""
PDF Data Extraction Module
Extracts text, tables, images, figures, and metadata from PDFs
Organizes data into structured JSON format for micro-course transformation
"""

import json
import re
import os
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict
import uuid

try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False
    print("Warning: PyMuPDF not available. Install with: pip install pymupdf")

try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False
    print("Warning: pdfplumber not available. Install with: pip install pdfplumber")

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("Warning: Pillow not available. Install with: pip install pillow")

# Multilingual support
try:
    from langdetect import detect, detect_langs, DetectorFactory
    from langdetect.lang_detect_exception import LangDetectException
    LANGDETECT_AVAILABLE = True
    # Set seed for consistent results
    DetectorFactory.seed = 0
except ImportError:
    LANGDETECT_AVAILABLE = False
    print("Warning: langdetect not available. Install with: pip install langdetect")

try:
    import chardet
    CHARDET_AVAILABLE = True
except ImportError:
    CHARDET_AVAILABLE = False
    print("Warning: chardet not available. Install with: pip install chardet")


class PDFExtractor:
    """Main class for extracting structured data from PDFs"""
    
    def __init__(self, pdf_path: str, output_dir: str = "output", 
                 enable_chart_extraction: bool = True, enable_ml_features: bool = True):
        """
        Initialize PDF extractor
        
        Args:
            pdf_path: Path to the PDF file
            output_dir: Directory for output files (images, JSON)
            enable_chart_extraction: Enable chart data extraction (can be slow)
            enable_ml_features: Enable ML feature engineering
        """
        self.pdf_path = pdf_path
        self.output_dir = output_dir
        self.images_dir = os.path.join(output_dir, "images")
        os.makedirs(self.images_dir, exist_ok=True)
        
        # Initialize document objects
        self.doc = None
        self.pdfplumber_doc = None
        self.content_blocks = []
        self.tables_data = []
        self.images_data = []
        self.figures_data = []
        self.metadata = {}
        
        # Text hierarchy detection
        self.font_size_stats = defaultdict(int)
        self.font_weight_stats = defaultdict(int)
        
        # Noise reduction
        self.header_footer_patterns = set()
        
        # Multilingual support
        self.document_languages = set()
        self.language_stats = defaultdict(int)
        self.writing_systems = defaultdict(int)
        
        # ML feature engineering flags
        self.enable_chart_extraction = enable_chart_extraction
        self.enable_ml_features = enable_ml_features
        
    def detect_language(self, text: str) -> Dict[str, Any]:
        """
        Detect language and writing system for text
        
        Args:
            text: Text to analyze
            
        Returns:
            Dict with language code, confidence, and writing system info
        """
        result = {
            "language_code": "unknown",
            "language_name": "Unknown",
            "confidence": 0.0,
            "writing_system": "ltr",
            "encoding": "utf-8"
        }
        
        if not text or len(text.strip()) < 3:
            return result
        
        # Detect encoding
        if CHARDET_AVAILABLE:
            try:
                text_bytes = text.encode('utf-8', errors='ignore')
                detected = chardet.detect(text_bytes)
                if detected and detected.get('encoding'):
                    result["encoding"] = detected['encoding'].lower()
            except:
                pass
        
        # Detect writing system
        writing_system = self._detect_writing_system(text)
        result["writing_system"] = writing_system
        self.writing_systems[writing_system] += 1
        
        # Detect language using langdetect
        if LANGDETECT_AVAILABLE:
            try:
                # Clean text for better detection (remove numbers, special chars)
                clean_text = re.sub(r'[0-9\W]+', ' ', text)
                clean_text = ' '.join(clean_text.split())
                
                if len(clean_text) >= 3:
                    # Get primary language
                    primary_lang = detect(clean_text)
                    
                    # Get confidence scores
                    lang_confidence = detect_langs(clean_text)
                    if lang_confidence:
                        confidence = lang_confidence[0].prob
                        result["language_code"] = primary_lang
                        result["language_name"] = self._get_language_name(primary_lang)
                        result["confidence"] = round(confidence, 3)
                        
                        # Track document languages
                        self.document_languages.add(primary_lang)
                        self.language_stats[primary_lang] += 1
            except (LangDetectException, Exception) as e:
                # Fallback to writing system based detection
                result["language_code"] = self._infer_language_from_writing_system(writing_system)
                result["language_name"] = self._get_language_name(result["language_code"])
                result["confidence"] = 0.5
        
        return result
    
    def _detect_writing_system(self, text: str) -> str:
        """
        Detect writing system direction and type
        
        Returns:
            'ltr', 'rtl', 'cjk', 'mixed'
        """
        if not text:
            return "ltr"
        
        # RTL scripts: Arabic, Hebrew, Persian, Urdu, etc.
        rtl_pattern = re.compile(r'[\u0590-\u05FF\u0600-\u06FF\u0700-\u074F\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]')
        
        # CJK scripts: Chinese, Japanese, Korean
        cjk_pattern = re.compile(r'[\u4E00-\u9FFF\u3400-\u4DBF\uF900-\uFAFF\u3000-\u303F\u3040-\u309F\u30A0-\u30FF\uAC00-\uD7AF]')
        
        # Latin scripts
        latin_pattern = re.compile(r'[a-zA-Z]')
        
        has_rtl = bool(rtl_pattern.search(text))
        has_cjk = bool(cjk_pattern.search(text))
        has_latin = bool(latin_pattern.search(text))
        
        if has_cjk:
            return "cjk"
        elif has_rtl and not has_latin:
            return "rtl"
        elif has_rtl and has_latin:
            return "mixed"
        else:
            return "ltr"
    
    def _infer_language_from_writing_system(self, writing_system: str) -> str:
        """Infer likely language from writing system"""
        mapping = {
            "rtl": "ar",  # Arabic (most common RTL)
            "cjk": "zh",  # Chinese (most common CJK)
            "ltr": "en",  # English (default LTR)
            "mixed": "en"  # Default for mixed
        }
        return mapping.get(writing_system, "en")
    
    def _get_language_name(self, lang_code: str) -> str:
        """Get language name from ISO 639-1 code"""
        language_names = {
            "ar": "Arabic", "de": "German", "en": "English", "es": "Spanish",
            "fr": "French", "it": "Italian", "ja": "Japanese", "ko": "Korean",
            "pt": "Portuguese", "ru": "Russian", "zh": "Chinese", "zh-cn": "Chinese (Simplified)",
            "zh-tw": "Chinese (Traditional)", "he": "Hebrew", "fa": "Persian",
            "hi": "Hindi", "tr": "Turkish", "pl": "Polish", "nl": "Dutch",
            "sv": "Swedish", "da": "Danish", "no": "Norwegian", "fi": "Finnish",
            "cs": "Czech", "hu": "Hungarian", "ro": "Romanian", "bg": "Bulgarian",
            "hr": "Croatian", "sr": "Serbian", "sk": "Slovak", "sl": "Slovenian",
            "uk": "Ukrainian", "el": "Greek", "th": "Thai", "vi": "Vietnamese",
            "id": "Indonesian", "ms": "Malay", "tl": "Tagalog", "sw": "Swahili"
        }
        return language_names.get(lang_code.lower(), lang_code.upper())
    
    def open_document(self):
        """Open PDF documents using both libraries"""
        if PYMUPDF_AVAILABLE:
            self.doc = fitz.open(self.pdf_path)
        else:
            raise ImportError("PyMuPDF is required. Install with: pip install pymupdf")
        
        if PDFPLUMBER_AVAILABLE:
            self.pdfplumber_doc = pdfplumber.open(self.pdf_path)
        else:
            raise ImportError("pdfplumber is required. Install with: pip install pdfplumber")
    
    def close_document(self):
        """Close PDF documents"""
        if self.doc:
            self.doc.close()
        if self.pdfplumber_doc:
            self.pdfplumber_doc.close()
    
    def extract_metadata(self) -> Dict[str, Any]:
        """Extract document-level metadata"""
        metadata = {
            "title": "",
            "author": "",
            "creation_date": "",
            "modification_date": "",
            "page_count": 0,
            "source_file": os.path.basename(self.pdf_path),
            "languages": [],
            "primary_language": "unknown",
            "writing_systems": []
        }
        
        if self.doc:
            meta = self.doc.metadata
            metadata.update({
                "title": meta.get("title", ""),
                "author": meta.get("author", ""),
                "creation_date": meta.get("creationDate", ""),
                "modification_date": meta.get("modDate", ""),
                "page_count": len(self.doc)
            })
            
            # Detect language from title if available
            if metadata["title"]:
                lang_info = self.detect_language(metadata["title"])
                if lang_info["language_code"] != "unknown":
                    self.document_languages.add(lang_info["language_code"])
        
        self.metadata = metadata
        return metadata
    
    def analyze_font_statistics(self, page_num: int):
        """Analyze font statistics for hierarchy detection"""
        if not self.doc:
            return
        
        page = self.doc[page_num]
        blocks = page.get_text("dict")
        
        for block in blocks["blocks"]:
            if "lines" in block:
                for line in block["lines"]:
                    for span in line["spans"]:
                        size = span.get("size", 0)
                        flags = span.get("flags", 0)
                        is_bold = flags & 16  # Bit 4 indicates bold
                        
                        if size > 0:
                            self.font_size_stats[size] += 1
                            if is_bold:
                                self.font_weight_stats["bold"] += 1
                            else:
                                self.font_weight_stats["normal"] += 1
    
    def classify_text_type(self, font_size: float, is_bold: bool, position: Dict, 
                          text: str, y_position: float, page_height: float = 841.89) -> str:
        """
        Classify text type based on characteristics with improved accuracy
        
        Returns tuple: (text_type, confidence_score)
        """
        confidence = 1.0
        text_clean = text.strip()
        
        # Get most common font size (baseline)
        if self.font_size_stats:
            most_common_size = max(self.font_size_stats.items(), key=lambda x: x[1])[0]
            size_ratio = font_size / most_common_size if most_common_size > 0 else 1
        else:
            size_ratio = 1
            confidence = 0.7  # Lower confidence without stats
        
        # Normalize y_position relative to page height
        relative_y = y_position / page_height if page_height > 0 else y_position / 841.89
        
        # Title detection - multiple strong indicators
        title_indicators = 0
        if y_position < 150:  # Top of page
            title_indicators += 1
        if size_ratio > 1.5:  # Much larger font
            title_indicators += 1
        if is_bold:
            title_indicators += 1
        if len(text_clean) < 100 and len(text_clean.split()) < 15:  # Short text
            title_indicators += 1
        if title_indicators >= 3:
            return "title"
        
        # Heading detection - larger, bold, often at section start
        if size_ratio > 1.3 and is_bold:
            # Check if it's a short line (typical heading)
            if len(text_clean.split()) < 20:
                return "heading"
        elif size_ratio > 1.1 and is_bold:
            if len(text_clean.split()) < 15:
                return "subheading"
        
        # Subheading - medium size, bold, shorter text
        if size_ratio > 1.05 and is_bold and len(text_clean.split()) < 25:
            return "subheading"
        
        # Author field - specific patterns
        author_patterns = [
            r'^By\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*',  # "By Firstname Lastname"
            r'^—\s*[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s*—',  # "— Author —"
            r'^Author:\s*[A-Z]',  # "Author: Name"
        ]
        for pattern in author_patterns:
            if re.match(pattern, text_clean, re.IGNORECASE):
                return "author"
        
        # Caption detection - near figures/tables, contains keywords
        caption_keywords = ["Figure", "Fig.", "Table", "Chart", "Source:", "Note:"]
        if any(keyword in text_clean for keyword in caption_keywords):
            if font_size < 10 or relative_y > 0.85:  # Small font or bottom of page
                return "caption"
        
        # Footnote detection - very small font, bottom of page, often numbered
        if font_size < 8:
            return "footnote"
        elif font_size < 9 and (relative_y > 0.9 or re.match(r'^\d+', text_clean)):
            return "footnote"
        
        # Metadata detection - specific patterns
        metadata_patterns = [
            r'^(Volume|Vol\.|ISSN|ISBN|Publisher|Editor|DOI:)',
            r'^\d{4}',  # Year at start
            r'^Page\s+\d+',  # Page number
        ]
        for pattern in metadata_patterns:
            if re.match(pattern, text_clean, re.IGNORECASE):
                return "metadata"
        
        # Box/Highlighted content - often has special formatting
        # (This would need additional detection from styling)
        
        # Default to paragraph
        return "paragraph"
    
    def extract_text_blocks(self, page_num: int) -> List[Dict[str, Any]]:
        """Extract text blocks with hierarchy and relationships"""
        if not self.doc:
            return []
        
        page = self.doc[page_num]
        page_width = page.rect.width
        page_height = page.rect.height
        blocks = page.get_text("dict")
        
        content_blocks = []
        block_id_map = {}
        
        # First pass: collect font statistics
        self.analyze_font_statistics(page_num)
        
        # Second pass: extract and classify blocks
        current_section = None
        block_index = 0
        
        for block_idx, block in enumerate(blocks["blocks"]):
            if "lines" not in block:
                continue
            
            # Combine all spans in block
            block_text_parts = []
            min_x = float('inf')
            min_y = float('inf')
            max_x = 0
            max_y = 0
            block_font_size = 0
            block_is_bold = False
            
            for line in block["lines"]:
                for span in line["spans"]:
                    text = span.get("text", "").strip()
                    if text:
                        block_text_parts.append(text)
                        
                        bbox = span["bbox"]
                        min_x = min(min_x, bbox[0])
                        min_y = min(min_y, bbox[1])
                        max_x = max(max_x, bbox[2])
                        max_y = max(max_y, bbox[3])
                        
                        font_size = span.get("size", 0)
                        flags = span.get("flags", 0)
                        is_bold = flags & 16
                        
                        if font_size > block_font_size:
                            block_font_size = font_size
                            block_is_bold = is_bold
            
            if not block_text_parts:
                continue
            
            block_text = " ".join(block_text_parts)
            
            # Clean text
            block_text = re.sub(r'\s+', ' ', block_text).strip()
            
            if not block_text or len(block_text) < 2:
                continue
            
            # Detect language and writing system
            lang_info = self.detect_language(block_text)
            
            # Classify text type
            text_type = self.classify_text_type(
                block_font_size, block_is_bold, 
                {"x0": min_x, "y0": min_y, "x1": max_x, "y1": max_y},
                block_text, min_y, page_height
            )
            
            # Update section context
            if text_type in ["title", "heading"]:
                current_section = block_index
            
            # Generate unique ID
            block_id = f"page_{page_num}_block_{block_index}"
            
            content_block = {
                "id": block_id,
                "type": "text",
                "hierarchy_level": self._get_hierarchy_level(text_type),
                "text_type": text_type,
                "content": block_text,
                "language": {
                    "code": lang_info["language_code"],
                    "name": lang_info["language_name"],
                    "confidence": lang_info["confidence"],
                    "writing_system": lang_info["writing_system"],
                    "encoding": lang_info["encoding"]
                },
                "position": {
                    "x0": round(min_x, 2),
                    "y0": round(min_y, 2),
                    "x1": round(max_x, 2),
                    "y1": round(max_y, 2)
                },
                "styling": {
                    "font_size": round(block_font_size, 2) if block_font_size > 0 else None,
                    "font_weight": "bold" if block_is_bold else "normal",
                    "alignment": self._detect_alignment(min_x, max_x, page_width)
                },
                "parent_id": None,
                "children_ids": [],
                "relationships": {
                    "figure_id": None,
                    "table_id": None,
                    "footnote_ids": []
                }
            }
            
            # Set parent relationship
            if current_section is not None and current_section != block_index:
                content_block["parent_id"] = f"page_{page_num}_block_{current_section}"
            
            content_blocks.append(content_block)
            block_id_map[block_idx] = block_id
            block_index += 1
        
        # Update children relationships
        for block in content_blocks:
            if block["parent_id"]:
                parent = next((b for b in content_blocks if b["id"] == block["parent_id"]), None)
                if parent:
                    parent["children_ids"].append(block["id"])
        
        # Join multi-column text
        content_blocks = self.join_multi_column_text(content_blocks, page_width)
        
        # Add ML features if enabled
        if self.enable_ml_features:
            total_pages = len(self.doc) if self.doc else 1
            for block in content_blocks:
                ml_features = self.compute_ml_features(
                    block, content_blocks, page_num, page_height, total_pages
                )
                block["ml_features"] = ml_features
        
        return content_blocks
    
    def join_multi_column_text(self, content_blocks: List[Dict], page_width: float) -> List[Dict]:
        """
        Join text blocks that span multiple columns (paragraphs split across columns)
        
        Args:
            content_blocks: List of content blocks from a page
            page_width: Width of the page
            
        Returns:
            List of content blocks with multi-column text joined
        """
        if not content_blocks:
            return content_blocks
        
        # Detect column boundaries by analyzing x-coordinate clusters
        x_positions = [block["position"]["x0"] for block in content_blocks]
        if not x_positions:
            return content_blocks
        
        # Simple column detection: assume 2-3 columns based on page width
        # Left column typically starts around 10% of page width
        # Right column typically starts around 50-55% of page width
        left_column_threshold = page_width * 0.15
        right_column_threshold = page_width * 0.50
        
        # Sort blocks by y-position (top to bottom)
        sorted_blocks = sorted(content_blocks, key=lambda b: (b["position"]["y0"], b["position"]["x0"]))
        
        joined_blocks = []
        i = 0
        
        while i < len(sorted_blocks):
            current_block = sorted_blocks[i].copy()
            
            # Only try to join paragraphs (not titles, headings, etc.)
            if current_block.get("text_type") not in ["paragraph", "author"]:
                joined_blocks.append(current_block)
                i += 1
                continue
            
            # Check if next block is a continuation in another column
            j = i + 1
            while j < len(sorted_blocks):
                next_block = sorted_blocks[j]
                
                # Check if blocks are potential continuations:
                # 1. Same text type
                # 2. Similar y-position (within threshold - e.g., 30 pixels)
                # 3. Different column (different x-position cluster)
                # 4. Similar styling
                y_diff = abs(next_block["position"]["y0"] - current_block["position"]["y1"])
                current_x = current_block["position"]["x0"]
                next_x = next_block["position"]["x0"]
                
                same_type = next_block.get("text_type") == current_block.get("text_type")
                similar_y = y_diff < 30  # Within 30 pixels vertically
                different_column = (
                    (current_x < left_column_threshold and next_x > right_column_threshold) or
                    (current_x > right_column_threshold and next_x < left_column_threshold) or
                    abs(current_x - next_x) > page_width * 0.35  # Significant horizontal difference
                )
                similar_styling = (
                    abs(current_block.get("styling", {}).get("font_size", 0) - 
                        next_block.get("styling", {}).get("font_size", 0)) < 1.0
                )
                
                # Check if current block doesn't end with sentence-ending punctuation
                current_text = current_block.get("content", "")
                ends_with_punctuation = current_text.rstrip().endswith(('.', '!', '?', ':', ';'))
                
                if (same_type and similar_y and different_column and similar_styling and 
                    not ends_with_punctuation):
                    # Merge blocks
                    current_block["content"] = current_block["content"] + " " + next_block.get("content", "")
                    
                    # Update bounding box to encompass both blocks
                    current_block["position"]["x0"] = min(
                        current_block["position"]["x0"],
                        next_block["position"]["x0"]
                    )
                    current_block["position"]["y0"] = min(
                        current_block["position"]["y0"],
                        next_block["position"]["y0"]
                    )
                    current_block["position"]["x1"] = max(
                        current_block["position"]["x1"],
                        next_block["position"]["x1"]
                    )
                    current_block["position"]["y1"] = max(
                        current_block["position"]["y1"],
                        next_block["position"]["y1"]
                    )
                    
                    # Mark as joined
                    current_block["is_multi_column"] = True
                    current_block["joined_blocks"] = [current_block["id"], next_block["id"]]
                    
                    j += 1
                else:
                    break
            
            joined_blocks.append(current_block)
            i = j if j > i + 1 else i + 1
        
        return joined_blocks
    
    def compute_ml_features(self, block: Dict, all_blocks: List[Dict], 
                           page_num: int, page_height: float, 
                           total_pages: int) -> Dict[str, Any]:
        """
        Compute ML-ready features for a content block
        
        Args:
            block: Content block dictionary
            all_blocks: All blocks from the same page
            page_num: Current page number
            page_height: Height of the page
            total_pages: Total number of pages in document
            
        Returns:
            Dictionary of ML features
        """
        features = {}
        text = block.get("content", "")
        
        # Text statistics
        features["char_count"] = len(text)
        features["word_count"] = len(text.split())
        features["sentence_count"] = len(re.split(r'[.!?]+', text)) - 1
        features["token_count"] = features["word_count"]  # Simple tokenization
        features["avg_word_length"] = (
            sum(len(word) for word in text.split()) / max(features["word_count"], 1)
        )
        features["has_numbers"] = bool(re.search(r'\d', text))
        features["has_special_chars"] = bool(re.search(r'[^\w\s]', text))
        features["has_capitalized_words"] = bool(re.search(r'\b[A-Z][a-z]+\b', text))
        features["ends_with_punctuation"] = bool(re.search(r'[.!?]$', text.strip()))
        
        # Position features (normalized)
        pos = block.get("position", {})
        features["normalized_x0"] = pos.get("x0", 0) / 600.0 if page_height > 0 else 0
        features["normalized_y0"] = pos.get("y0", 0) / page_height if page_height > 0 else 0
        features["normalized_x1"] = pos.get("x1", 0) / 600.0 if page_height > 0 else 0
        features["normalized_y1"] = pos.get("y1", 0) / page_height if page_height > 0 else 0
        features["normalized_center_x"] = (
            (pos.get("x0", 0) + pos.get("x1", 0)) / 2.0 / 600.0 if page_height > 0 else 0
        )
        features["normalized_center_y"] = (
            (pos.get("y0", 0) + pos.get("y1", 0)) / 2.0 / page_height if page_height > 0 else 0
        )
        features["relative_to_page_center"] = abs(features["normalized_center_x"] - 0.5)
        
        # Document-level position
        features["page_number"] = page_num + 1
        features["relative_page_position"] = (page_num + 1) / max(total_pages, 1)
        features["is_first_page"] = page_num == 0
        features["is_last_page"] = page_num == total_pages - 1
        
        # Context features - surrounding blocks
        block_y = pos.get("y0", 0)
        previous_blocks = [b for b in all_blocks if b.get("position", {}).get("y0", 0) < block_y]
        next_blocks = [b for b in all_blocks if b.get("position", {}).get("y0", 0) > block_y]
        
        if previous_blocks:
            prev_block = max(previous_blocks, key=lambda b: b.get("position", {}).get("y0", 0))
            features["previous_block_type"] = prev_block.get("text_type", "unknown")
            features["previous_block_hierarchy"] = prev_block.get("hierarchy_level", 5)
            features["distance_to_previous"] = block_y - prev_block.get("position", {}).get("y1", 0)
        else:
            features["previous_block_type"] = None
            features["previous_block_hierarchy"] = None
            features["distance_to_previous"] = None
        
        if next_blocks:
            next_block = min(next_blocks, key=lambda b: b.get("position", {}).get("y0", 0))
            features["next_block_type"] = next_block.get("text_type", "unknown")
            features["next_block_hierarchy"] = next_block.get("hierarchy_level", 5)
            features["distance_to_next"] = next_block.get("position", {}).get("y0", 0) - pos.get("y1", 0)
        else:
            features["next_block_type"] = None
            features["next_block_hierarchy"] = None
            features["distance_to_next"] = None
        
        # Section context - blocks with same parent
        parent_id = block.get("parent_id")
        if parent_id:
            section_blocks = [b for b in all_blocks if b.get("parent_id") == parent_id]
            features["section_block_count"] = len(section_blocks)
            features["section_position"] = (
                sorted(section_blocks, key=lambda b: b.get("position", {}).get("y0", 0))
                .index(block) / max(len(section_blocks), 1)
            )
        else:
            features["section_block_count"] = 0
            features["section_position"] = 0.0
        
        # Styling features
        styling = block.get("styling", {})
        features["font_size"] = styling.get("font_size", 0)
        features["font_weight_bold"] = 1 if styling.get("font_weight") == "bold" else 0
        features["alignment_left"] = 1 if styling.get("alignment") == "left" else 0
        features["alignment_center"] = 1 if styling.get("alignment") == "center" else 0
        features["alignment_right"] = 1 if styling.get("alignment") == "right" else 0
        
        # Hierarchy features
        features["hierarchy_level"] = block.get("hierarchy_level", 5)
        features["is_title"] = 1 if block.get("text_type") == "title" else 0
        features["is_heading"] = 1 if block.get("text_type") in ["heading", "subheading"] else 0
        features["is_paragraph"] = 1 if block.get("text_type") == "paragraph" else 0
        
        # Relationship features
        relationships = block.get("relationships", {})
        features["has_table"] = 1 if relationships.get("table_id") else 0
        features["has_figure"] = 1 if relationships.get("figure_id") else 0
        features["has_footnotes"] = 1 if relationships.get("footnote_ids") else 0
        features["footnote_count"] = len(relationships.get("footnote_ids", []))
        
        # Language features
        language = block.get("language", {})
        features["language_code"] = language.get("code", "unknown")
        features["language_confidence"] = language.get("confidence", 0.0)
        features["writing_system_ltr"] = 1 if language.get("writing_system") == "ltr" else 0
        features["writing_system_rtl"] = 1 if language.get("writing_system") == "rtl" else 0
        
        return features
    
    def extract_chart_data(self, figure_image_path: str, embedded_text: List[Dict] = None) -> Dict[str, Any]:
        """
        Extract structured data from chart images using image processing
        
        Args:
            figure_image_path: Path to the extracted figure image
            embedded_text: List of text overlays from PDF (if available)
            
        Returns:
            Dictionary with chart data structure
        """
        if not self.enable_chart_extraction:
            return None
        
        try:
            import cv2
            import numpy as np
        except ImportError:
            print("Warning: OpenCV not available. Chart data extraction disabled.")
            return None
        
        if not os.path.exists(figure_image_path):
            return None
        
        chart_data = {
            "chart_type": "unknown",
            "series": [],
            "axes": {},
            "legend": {},
            "extraction_method": "image_processing",
            "confidence": 0.0
        }
        
        try:
            # Load image
            img = cv2.imread(figure_image_path)
            if img is None:
                return None
            
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            height, width = gray.shape
            
            # Detect chart type - look for bar patterns
            # This is a simplified detection - can be enhanced
            edges = cv2.Canny(gray, 50, 150)
            
            # Detect horizontal lines (axis lines)
            horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (40, 1))
            horizontal_lines = cv2.morphologyEx(edges, cv2.MORPH_OPEN, horizontal_kernel)
            
            # Detect vertical lines (bar edges)
            vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 40))
            vertical_lines = cv2.morphologyEx(edges, cv2.MORPH_OPEN, vertical_kernel)
            
            # Count vertical structures (potential bars)
            vertical_count = np.sum(vertical_lines > 0) // (height // 10)
            
            if vertical_count > 5:  # Likely a bar chart
                chart_data["chart_type"] = "bar"
                chart_data["confidence"] = 0.6
                
                # Try to extract data from embedded text if available
                if embedded_text:
                    # Look for patterns like state abbreviations, numbers, years
                    data_points = []
                    series_names = []
                    
                    for text_item in embedded_text:
                        text = text_item.get("text", "")
                        # Look for year patterns
                        year_match = re.search(r'\b(19|20)\d{2}\b', text)
                        if year_match:
                            series_names.append(year_match.group())
                        
                        # Look for percentage or numeric values
                        num_match = re.search(r'(\d+(?:\.\d+)?)\s*%', text)
                        if num_match:
                            value = float(num_match.group(1))
                            # Try to find associated category (state abbreviation, etc.)
                            # This is simplified - would need more sophisticated parsing
                            data_points.append({
                                "value": value,
                                "unit": "percentage",
                                "text_context": text
                            })
                    
                    if series_names or data_points:
                        # Create series structure
                        if series_names:
                            for series_name in set(series_names):
                                chart_data["series"].append({
                                    "name": series_name,
                                    "data_points": [dp for dp in data_points if series_name in dp.get("text_context", "")]
                                })
                        else:
                            chart_data["series"].append({
                                "name": "default",
                                "data_points": data_points
                            })
            
            # Store axis information if detected
            if len(horizontal_lines) > 0:
                chart_data["axes"]["has_horizontal_axis"] = True
            if len(vertical_lines) > 0:
                chart_data["axes"]["has_vertical_axis"] = True
            
        except Exception as e:
            print(f"Warning: Chart data extraction failed for {figure_image_path}: {e}")
            return None
        
        return chart_data if chart_data.get("series") or chart_data.get("chart_type") != "unknown" else None
    
    def _get_hierarchy_level(self, text_type: str) -> int:
        """Get hierarchy level for text type"""
        hierarchy_map = {
            "title": 1,
            "heading": 2,
            "subheading": 3,
            "author": 4,
            "paragraph": 5,
            "caption": 6,
            "metadata": 6,
            "footnote": 7
        }
        return hierarchy_map.get(text_type, 5)
    
    def _detect_alignment(self, x0: float, x1: float, page_width: float) -> str:
        """Detect text alignment"""
        center = page_width / 2
        left_threshold = page_width * 0.2
        right_threshold = page_width * 0.8
        
        block_center = (x0 + x1) / 2
        
        if abs(block_center - center) < page_width * 0.1:
            return "center"
        elif x0 < left_threshold:
            return "left"
        elif x1 > right_threshold:
            return "right"
        else:
            return "left"
    
    def extract_tables(self, page_num: int) -> List[Dict[str, Any]]:
        """Extract tables from page using pdfplumber"""
        if not PDFPLUMBER_AVAILABLE or not self.pdfplumber_doc:
            return []
        
        tables_data = []
        page = self.pdfplumber_doc.pages[page_num]
        
        # Extract tables
        tables = page.extract_tables()
        
        for table_idx, table in enumerate(tables):
            if not table or len(table) == 0:
                continue
            
            # Find table bounding box (approximate)
            # This is a simplified version - pdfplumber doesn't always provide exact coordinates
            table_id = f"page_{page_num}_table_{table_idx}"
            
            # Try to find table in page using text search
            table_start_text = None
            for row in table:
                if row and any(cell and cell.strip() for cell in row):
                    table_start_text = next((cell for cell in row if cell and cell.strip()), None)
                    break
            
            # Get table position (approximate)
            if table_start_text:
                try:
                    words = page.extract_words()
                    for word in words:
                        if table_start_text[:20] in word.get("text", ""):
                            bbox = (word["x0"], word["top"], word["x1"], word["bottom"])
                            break
                    else:
                        bbox = (50, 100, page.width - 50, page.height - 100)
                except:
                    bbox = (50, 100, page.width - 50, page.height - 100)
            else:
                bbox = (50, 100, page.width - 50, page.height - 100)
            
            # Determine if first row is header
            has_header = False
            if len(table) > 1:
                first_row = table[0]
                second_row = table[1] if len(table) > 1 else []
                # Heuristic: if first row has mostly text and second has data, it's a header
                first_row_text_ratio = sum(1 for cell in first_row if cell and isinstance(cell, str) and cell.strip()) / max(len(first_row), 1)
                if first_row_text_ratio > 0.7:
                    has_header = True
            
            # Structure table data
            table_data = {
                "id": table_id,
                "caption": None,  # Will be filled by relationship mapping
                "position": {
                    "x0": round(bbox[0], 2),
                    "y0": round(bbox[1], 2),
                    "x1": round(bbox[2], 2),
                    "y1": round(bbox[3], 2)
                },
                "structure": {
                    "rows": len(table),
                    "columns": max(len(row) for row in table) if table else 0,
                    "has_header": has_header
                },
                "data": []
            }
            
            # Extract cells
            for row_idx, row in enumerate(table):
                for col_idx, cell in enumerate(row):
                    if cell is not None:
                        cell_content = str(cell).strip() if cell else ""
                        if cell_content:
                            # Detect language for cell content
                            lang_info = self.detect_language(cell_content)
                            
                            table_data["data"].append({
                                "row": row_idx,
                                "column": col_idx,
                                "content": cell_content,
                                "language": {
                                    "code": lang_info["language_code"],
                                    "name": lang_info["language_name"],
                                    "confidence": lang_info["confidence"],
                                    "writing_system": lang_info["writing_system"]
                                },
                                "is_header": has_header and row_idx == 0,
                                "merged_cells": None  # pdfplumber doesn't always preserve this
                            })
            
            tables_data.append(table_data)
        
        return tables_data
    
    def extract_images_and_figures(self, page_num: int) -> Tuple[List[Dict], List[Dict]]:
        """Extract images and figures from page"""
        if not self.doc:
            return [], []
        
        page = self.doc[page_num]
        images_data = []
        figures_data = []
        
        # Get image list
        image_list = page.get_images(full=True)
        
        # Get all text with positions for overlay detection
        text_dict = page.get_text("dict")
        text_blocks_positions = []
        
        for block in text_dict.get("blocks", []):
            if "lines" in block:
                for line in block["lines"]:
                    for span in line["spans"]:
                        bbox = span["bbox"]
                        text_blocks_positions.append({
                            "text": span.get("text", ""),
                            "bbox": bbox,
                            "x0": bbox[0],
                            "y0": bbox[1],
                            "x1": bbox[2],
                            "y1": bbox[3]
                        })
        
        # Process each image
        for img_idx, img in enumerate(image_list):
            xref = img[0]
            
            try:
                # Extract image
                base_image = self.doc.extract_image(xref)
                image_bytes = base_image["image"]
                image_ext = base_image["ext"]
                
                # Get image placement information
                image_rects = page.get_image_rects(xref)
                
                if not image_rects:
                    continue
                
                # Use first placement
                rect = image_rects[0]
                
                # Save image
                image_filename = f"page_{page_num}_image_{img_idx}.{image_ext}"
                image_path = os.path.join(self.images_dir, image_filename)
                
                with open(image_path, "wb") as img_file:
                    img_file.write(image_bytes)
                
                # Find overlapping or nearby text (labels, annotations)
                embedded_text = []
                image_bbox = {
                    "x0": rect.x0,
                    "y0": rect.y1,  # PDF coordinates are bottom-up
                    "x1": rect.x1,
                    "y1": rect.y0
                }
                
                # Check for text that overlaps or is very close to image
                margin = 10  # pixels
                for text_block in text_blocks_positions:
                    # Check if text overlaps or is near image
                    if (text_block["x0"] >= image_bbox["x0"] - margin and
                        text_block["x1"] <= image_bbox["x1"] + margin and
                        text_block["y0"] >= image_bbox["y0"] - margin and
                        text_block["y1"] <= image_bbox["y1"] + margin):
                        
                        embedded_text.append({
                            "text": text_block["text"],
                            "position": {
                                "x0": round(text_block["x0"], 2),
                                "y0": round(text_block["y0"], 2),
                                "x1": round(text_block["x1"], 2),
                                "y1": round(text_block["y1"], 2)
                            },
                            "relative_position": {
                                "x": round(text_block["x0"] - image_bbox["x0"], 2),
                                "y": round(text_block["y0"] - image_bbox["y0"], 2)
                            }
                        })
                
                # Classify as image or figure based on size and position
                image_area = (rect.x1 - rect.x0) * (rect.y1 - rect.y0)
                page_area = page.rect.width * page.rect.height
                
                # Determine type
                if image_area > page_area * 0.1:  # Large images are likely figures/charts
                    # Detect if it's a chart (bar chart, line chart, etc.)
                    # Check embedded text for chart indicators
                    has_chart_indicators = any(
                        keyword in text_item.get("text", "").lower()
                        for text_item in embedded_text
                        for keyword in ["chart", "graph", "bar", "axis", "percentage", "%"]
                    )
                    
                    image_type = "chart" if has_chart_indicators else "diagram"
                    
                    image_id = f"page_{page_num}_figure_{len(figures_data)}"
                    figure_data = {
                        "id": image_id,
                        "type": image_type,
                        "chart_type": None,  # Will be set if chart data extracted
                        "caption": None,  # Will be filled by relationship mapping
                        "position": {
                            "x0": round(rect.x0, 2),
                            "y0": round(rect.y1, 2),
                            "x1": round(rect.x1, 2),
                            "y1": round(rect.y0, 2)
                        },
                        "file_path": image_path,
                        "embedded_text": embedded_text,
                        "chart_data": None  # Will be populated if chart extraction succeeds
                    }
                    
                    # Extract chart data if it's a chart
                    if image_type == "chart" and self.enable_chart_extraction:
                        chart_data = self.extract_chart_data(image_path, embedded_text)
                        if chart_data:
                            figure_data["chart_data"] = chart_data
                            figure_data["chart_type"] = chart_data.get("chart_type", "unknown")
                    
                    figures_data.append(figure_data)
                else:
                    # Small images (logos, icons)
                    image_type = "logo" if image_area < page_area * 0.05 else "photograph"
                    
                    image_id = f"page_{page_num}_image_{len(images_data)}"
                    image_data = {
                        "id": image_id,
                        "type": image_type,
                        "caption": None,
                        "position": {
                            "x0": round(rect.x0, 2),
                            "y0": round(rect.y1, 2),
                            "x1": round(rect.x1, 2),
                            "y1": round(rect.y0, 2)
                        },
                        "file_path": image_path,
                        "embedded_text": embedded_text
                    }
                    images_data.append(image_data)
            
            except Exception as e:
                print(f"Warning: Could not extract image {img_idx} from page {page_num}: {e}")
                continue
        
        return images_data, figures_data
    
    def map_relationships(self, page_num: int, content_blocks: List[Dict], 
                         tables: List[Dict], images: List[Dict], figures: List[Dict]):
        """Map relationships between content blocks, tables, figures, and captions"""
        
        # Find captions for figures and tables
        for figure in figures:
            figure_bbox = figure["position"]
            # Look for text blocks below the figure that contain "Figure", "Chart", etc.
            for block in content_blocks:
                if block["text_type"] == "caption":
                    block_bbox = block["position"]
                    # Check if caption is directly below figure
                    if (block_bbox["y0"] > figure_bbox["y1"] and
                        abs(block_bbox["x0"] - figure_bbox["x0"]) < 50):
                        figure["caption"] = block["content"]
                        # Link block to figure
                        block["relationships"]["figure_id"] = figure["id"]
                        break
        
        for table in tables:
            table_bbox = table["position"]
            # Look for captions near tables
            for block in content_blocks:
                if block["text_type"] == "caption":
                    block_bbox = block["position"]
                    if (abs(block_bbox["y0"] - table_bbox["y0"]) < 30 or
                        abs(block_bbox["y1"] - table_bbox["y1"]) < 30):
                        if abs(block_bbox["x0"] - table_bbox["x0"]) < 50:
                            table["caption"] = block["content"]
                            block["relationships"]["table_id"] = table["id"]
                            break
        
        # Link footnotes
        footnote_blocks = [b for b in content_blocks if b["text_type"] == "footnote"]
        for block in content_blocks:
            if block["text_type"] != "footnote":
                # Find footnote references in text (numbers in superscript or parentheses)
                text = block["content"]
                footnote_refs = re.findall(r'\d+', text)  # Simple heuristic
                for ref in footnote_refs[:3]:  # Limit to first 3 matches
                    # Find corresponding footnote (this is simplified)
                    for footnote in footnote_blocks:
                        if ref in footnote["content"]:
                            if footnote["id"] not in block["relationships"]["footnote_ids"]:
                                block["relationships"]["footnote_ids"].append(footnote["id"])
    
    def reduce_noise(self, all_content_blocks: List[List[Dict]]):
        """Remove noise like repeated headers/footers"""
        if not all_content_blocks:
            return
        
        # Collect text from first and last blocks of pages (potential headers/footers)
        first_blocks = []
        last_blocks = []
        
        for page_blocks in all_content_blocks:
            if page_blocks:
                first_blocks.append(page_blocks[0]["content"][:50])  # First 50 chars
                last_blocks.append(page_blocks[-1]["content"][:50])  # Last block first 50 chars
        
        # Find repeated patterns
        from collections import Counter
        first_counter = Counter(first_blocks)
        last_counter = Counter(last_blocks)
        
        # Identify headers/footers (appearing in >50% of pages)
        threshold = len(all_content_blocks) * 0.5
        header_patterns = {text for text, count in first_counter.items() if count > threshold}
        footer_patterns = {text for text, count in last_counter.items() if count > threshold}
        
        # Remove identified headers/footers from middle pages
        for page_idx, page_blocks in enumerate(all_content_blocks):
            if page_idx == 0 or page_idx == len(all_content_blocks) - 1:
                continue  # Keep first and last page headers/footers
            
            page_blocks[:] = [block for block in page_blocks 
                            if not (block["content"][:50] in header_patterns or
                                   block["content"][:50] in footer_patterns)]
    
    def extract_all(self) -> Dict[str, Any]:
        """Extract all data from PDF and return structured JSON"""
        print(f"Opening PDF: {self.pdf_path}")
        self.open_document()
        
        try:
            # Extract metadata
            print("Extracting metadata...")
            metadata = self.extract_metadata()
            
            # Extract content from all pages
            all_pages_data = []
            all_content_blocks = []
            
            num_pages = len(self.doc) if self.doc else 0
            print(f"Processing {num_pages} pages...")
            
            for page_num in range(num_pages):
                print(f"  Processing page {page_num + 1}/{num_pages}...")
                
                # Extract text blocks
                content_blocks = self.extract_text_blocks(page_num)
                
                # Extract tables
                tables = self.extract_tables(page_num)
                
                # Extract images and figures
                images, figures = self.extract_images_and_figures(page_num)
                
                # Map relationships
                self.map_relationships(page_num, content_blocks, tables, images, figures)
                
                # Get page dimensions
                if self.doc:
                    page = self.doc[page_num]
                    page_width = page.rect.width
                    page_height = page.rect.height
                else:
                    page_width = page_height = 0
                
                page_data = {
                    "page_number": page_num + 1,
                    "dimensions": {
                        "width": round(page_width, 2),
                        "height": round(page_height, 2)
                    },
                    "content_blocks": content_blocks,
                    "tables": tables,
                    "images": images,
                    "figures": figures
                }
                
                all_pages_data.append(page_data)
                all_content_blocks.append(content_blocks)
            
            # Reduce noise
            print("Reducing noise...")
            self.reduce_noise(all_content_blocks)
            
            # Rebuild page data after noise reduction
            for page_num, page_data in enumerate(all_pages_data):
                page_data["content_blocks"] = all_content_blocks[page_num]
            
            # Update metadata with language statistics
            if self.document_languages:
                # Sort languages by frequency
                sorted_languages = sorted(self.language_stats.items(), key=lambda x: -x[1])
                metadata["languages"] = [
                    {
                        "code": lang_code,
                        "name": self._get_language_name(lang_code),
                        "frequency": count,
                        "percentage": round((count / sum(self.language_stats.values())) * 100, 2)
                    }
                    for lang_code, count in sorted_languages
                ]
                metadata["primary_language"] = sorted_languages[0][0] if sorted_languages else "unknown"
            else:
                metadata["languages"] = []
                metadata["primary_language"] = "unknown"
            
            # Add writing systems information
            if self.writing_systems:
                metadata["writing_systems"] = [
                    {
                        "system": ws,
                        "count": count,
                        "percentage": round((count / sum(self.writing_systems.values())) * 100, 2)
                    }
                    for ws, count in sorted(self.writing_systems.items(), key=lambda x: -x[1])
                ]
            else:
                metadata["writing_systems"] = []
            
            # Build final structure
            result = {
                "document": {
                    "metadata": metadata,
                    "pages": all_pages_data
                }
            }
            
            return result
        
        finally:
            self.close_document()
    
    def save_json(self, data: Dict[str, Any], output_path: str = None):
        """Save extracted data to JSON file"""
        if output_path is None:
            output_path = os.path.join(self.output_dir, "extracted_data.json")
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"\nExtraction complete! Data saved to: {output_path}")
        print(f"Images saved to: {self.images_dir}")


def main():
    """Main function for command-line usage"""
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description="Extract structured data from PDF files")
    parser.add_argument("pdf_path", help="Path to the PDF file")
    parser.add_argument("output_dir", nargs="?", default="output", help="Output directory (default: output)")
    parser.add_argument("--no-chart-extraction", action="store_true", 
                       help="Disable chart data extraction (faster)")
    parser.add_argument("--no-ml-features", action="store_true",
                       help="Disable ML feature engineering (faster)")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.pdf_path):
        print(f"Error: PDF file not found: {args.pdf_path}")
        sys.exit(1)
    
    enable_chart = not args.no_chart_extraction
    enable_ml = not args.no_ml_features
    
    extractor = PDFExtractor(args.pdf_path, args.output_dir, 
                           enable_chart_extraction=enable_chart,
                           enable_ml_features=enable_ml)
    data = extractor.extract_all()
    extractor.save_json(data)
    
    # Optionally export to CSV if pandas is available
    try:
        from csv_exporter import CSVExporter
        print("\nExporting to CSV format...")
        exporter = CSVExporter(data, args.output_dir)
        exporter.export_all(single_file=True)  # Export to single file
    except ImportError:
        print("\nNote: CSV export requires pandas. Install with: pip install pandas")
    except Exception as e:
        print(f"\nNote: CSV export failed: {e}")


if __name__ == "__main__":
    main()

