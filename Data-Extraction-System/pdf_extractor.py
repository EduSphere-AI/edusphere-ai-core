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
    
    def __init__(self, pdf_path: str, output_dir: str = "output"):
        """
        Initialize PDF extractor
        
        Args:
            pdf_path: Path to the PDF file
            output_dir: Directory for output files (images, JSON)
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
                          text: str, y_position: float) -> str:
        """Classify text type based on characteristics"""
        # Get most common font size (baseline)
        if self.font_size_stats:
            most_common_size = max(self.font_size_stats.items(), key=lambda x: x[1])[0]
            size_ratio = font_size / most_common_size if most_common_size > 0 else 1
        else:
            size_ratio = 1
        
        # Check if it's at the top of page (likely title/header)
        if y_position < 100 and size_ratio > 1.2:
            return "title"
        
        # Check if it's a heading (larger, bold)
        if size_ratio > 1.3 and is_bold:
            return "heading"
        elif size_ratio > 1.1 and is_bold:
            return "subheading"
        
        # Check if it's very small (footnote, caption)
        if font_size < 8:
            return "footnote"
        elif font_size < 9:
            # Check if it's near bottom or contains "Figure" or "Source"
            if "Figure" in text or "Source" in text or y_position > 700:
                return "caption"
            return "footnote"
        
        # Check for metadata patterns
        if re.match(r'^(Volume|ISSN|Publisher|Editor)', text, re.IGNORECASE):
            return "metadata"
        
        # Check for author patterns
        if re.match(r'^By\s+\w+', text, re.IGNORECASE):
            return "author"
        
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
                block_text, min_y
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
        
        return content_blocks
    
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
                    image_type = "chart" if "chart" in image_filename.lower() else "diagram"
                    
                    image_id = f"page_{page_num}_figure_{len(figures_data)}"
                    figure_data = {
                        "id": image_id,
                        "type": image_type,
                        "caption": None,  # Will be filled by relationship mapping
                        "position": {
                            "x0": round(rect.x0, 2),
                            "y0": round(rect.y1, 2),
                            "x1": round(rect.x1, 2),
                            "y1": round(rect.y0, 2)
                        },
                        "file_path": image_path,
                        "embedded_text": embedded_text
                    }
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
    
    if len(sys.argv) < 2:
        print("Usage: python pdf_extractor.py <pdf_path> [output_dir]")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "output"
    
    if not os.path.exists(pdf_path):
        print(f"Error: PDF file not found: {pdf_path}")
        sys.exit(1)
    
    extractor = PDFExtractor(pdf_path, output_dir)
    data = extractor.extract_all()
    extractor.save_json(data)


if __name__ == "__main__":
    main()

