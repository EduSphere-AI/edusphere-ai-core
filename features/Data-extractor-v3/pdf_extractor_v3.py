#!/usr/bin/env python3
"""
PDF Extractor V3 - Unified extraction with structure, positions, and complete coverage
Combines the best features of all previous extractors for well-structured, logical output.
"""

import json
import re
import base64
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional
from dataclasses import dataclass, field
from collections import defaultdict

try:
    import fitz  # PyMuPDF
except ImportError:
    print("Error: PyMuPDF not installed. Install with: pip install pymupdf")
    exit(1)

try:
    import pdfplumber
except ImportError:
    print("Error: pdfplumber not installed. Install with: pip install pdfplumber")
    exit(1)

try:
    from PIL import Image
except ImportError:
    print("Error: Pillow not installed. Install with: pip install Pillow")
    exit(1)

try:
    import nltk
    from nltk.tokenize import sent_tokenize, word_tokenize
    from nltk.corpus import stopwords
    NLTK_AVAILABLE = True
    # Download required NLTK data
    try:
        nltk.data.find('tokenizers/punkt')
    except LookupError:
        nltk.download('punkt', quiet=True)
    try:
        nltk.data.find('corpora/stopwords')
    except LookupError:
        nltk.download('stopwords', quiet=True)
except ImportError:
    NLTK_AVAILABLE = False
    print("Warning: NLTK not available. Install with: pip install nltk")
    print("  ML text boundary detection will use fallback methods.")

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.cluster import DBSCAN
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    print("Warning: scikit-learn not available. Install with: pip install scikit-learn")
    print("  Advanced ML clustering will be disabled.")


@dataclass
class ContentItem:
    """Represents a single content item in the document flow."""
    type: str  # 'section', 'table', 'image', 'text_block'
    page: int
    y_position: float  # For sorting by document flow
    data: Dict[str, Any] = field(default_factory=dict)


class MLTextBoundaryDetector:
    """ML-based text boundary detection for identifying where text starts and ends."""
    
    def __init__(self, extractor=None):
        self.vectorizer = None
        self.extractor = extractor  # Reference to PDFExtractorV3 for utility methods
        if SKLEARN_AVAILABLE:
            self.vectorizer = TfidfVectorizer(max_features=100, stop_words='english', ngram_range=(1, 2))
    
    def is_metadata(self, text: str) -> bool:
        """Check if text is metadata - delegates to extractor or uses static method."""
        if self.extractor:
            return self.extractor.is_metadata(text)
        return PDFExtractorV3.is_metadata(text)
    
    def detect_title_or_subtitle(self, text: str, font_size: float, avg_font_size: float, 
                                 is_first_in_paragraph: bool = False) -> Optional[str]:
        """Detect if text block is a title or subtitle within a paragraph."""
        if not text or len(text.strip()) < 3:
            return None
        
        text = text.strip()
        
        # Exclude citations, footnotes, and metadata
        citation_patterns = [
            r'^\d+\s+Cf\.',  # "8 Cf."
            r'^Cf\.',  # "Cf."
            r'^See\s+',  # "See ..."
            r'^Source:',  # "Source:"
            r'^Note[s]?:',  # "Note:"
            r'^©\s+',  # Copyright
            r'^DOI:',  # DOI
            r'^JEL:',  # JEL codes
            r'^\d+\s+DIW',  # Page numbers
        ]
        
        if any(re.match(pattern, text, re.IGNORECASE) for pattern in citation_patterns):
            return None
        
        # Exclude common sentence patterns
        if text.endswith(',') or (text.endswith('.') and not text.endswith('..')):
            return None
        
        # Title/subtitle characteristics:
        # 1. Larger font size (at least 10% larger) OR ends with colon
        # 2. Short to medium length (typically < 100 chars)
        # 3. Title case or ALL CAPS
        # 4. Ends with colon (strong indicator)
        # 5. Doesn't look like a sentence (limited lowercase words)
        
        is_large_font = font_size > avg_font_size * 1.1
        is_short = len(text) < 100
        is_very_short = len(text) < 60
        ends_with_colon = text.endswith(':')
        is_all_caps = text.isupper() and len(text.split()) > 1
        # Title case: starts with capital, mostly capitals in first few words
        words = text.split()
        first_words_caps = len([w for w in words[:3] if w and w[0].isupper()]) >= 2
        has_many_lowercase = len(re.findall(r'\b[a-z]{3,}\b', text)) > 2  # Many lowercase words
        
        # Title detection (strong indicators)
        if ends_with_colon and is_short and (is_large_font or is_all_caps or first_words_caps):
            return "title"
        
        if is_large_font and is_very_short and (is_all_caps or (first_words_caps and not has_many_lowercase)):
            return "title"
        
        # Patterns like "Projection of tax revenue" or "Scenario I:" or "Box 1"
        if is_very_short and first_words_caps and not has_many_lowercase and not text.endswith('.'):
            # Check for common title patterns
            title_patterns = [
                r'^(Projection|Scenario|Box|Table|Figure|Section)\s+',
                r'^[A-Z][a-z]+(\s+[A-Z][a-z]+)+\s*:',  # "Title Case Text:"
                r'^[A-Z][a-z]+\s+of\s+[A-Z]',  # "Projection of Tax"
            ]
            if ends_with_colon or (is_first_in_paragraph and len(words) <= 5):
                if any(re.match(pattern, text, re.IGNORECASE) for pattern in title_patterns):
                    return "title"
                # Also check if it's a standalone title-like phrase
                if len(words) <= 4 and not has_many_lowercase:
                    return "title"
        
        # Subtitle detection (weaker but still clear)
        if ends_with_colon and is_short and first_words_caps and not has_many_lowercase:
            return "subtitle"
        
        if is_short and is_all_caps and is_first_in_paragraph:
            return "subtitle"
        
        return None
    
    def detect_column_boundaries(self, text_blocks: List[Dict[str, Any]]) -> List[float]:
        """Detect column boundaries by analyzing X-position gaps (invisible columns)."""
        if not text_blocks:
            return []
        
        # Collect all X positions (left edges of text blocks)
        x_positions = []
        for block in text_blocks:
            x0 = block.get("position", {}).get("x0", 0)
            if x0 > 0:
                x_positions.append(x0)
        
        if not x_positions:
            return []
        
        # Sort and find clusters of X positions (columns)
        x_positions_sorted = sorted(set(x_positions))
        
        # Find large gaps in X positions (column boundaries)
        x_gaps = []
        for i in range(len(x_positions_sorted) - 1):
            gap = x_positions_sorted[i + 1] - x_positions_sorted[i]
            x_gaps.append((x_positions_sorted[i], gap))
        
        # Sort gaps by size and identify column boundaries
        x_gaps_sorted = sorted(x_gaps, key=lambda x: x[1], reverse=True)
        
        # Typical column gap is much larger than normal spacing
        # Look for gaps that are significantly larger than typical spacing
        if x_gaps_sorted:
            largest_gap = x_gaps_sorted[0][1]
            # Column boundary is typically > 50 pixels (adjust based on page width)
            column_boundary_threshold = max(50, largest_gap * 0.3)
            
            column_boundaries = []
            for x_pos, gap in x_gaps_sorted:
                if gap > column_boundary_threshold:
                    # Column boundary is between x_pos and x_pos + gap
                    boundary = x_pos + gap / 2
                    column_boundaries.append(boundary)
            
            # Sort and return unique boundaries
            return sorted(set(column_boundaries))
        
        return []
    
    def assign_blocks_to_columns(self, text_blocks: List[Dict[str, Any]], 
                                 column_boundaries: List[float]) -> Dict[int, List[Dict[str, Any]]]:
        """Assign text blocks to columns based on their X position."""
        columns = defaultdict(list)
        
        for block in text_blocks:
            x_center = (block.get("position", {}).get("x0", 0) + 
                       block.get("position", {}).get("x1", 0)) / 2
            
            # Find which column this block belongs to
            column_idx = 0
            for i, boundary in enumerate(column_boundaries):
                if x_center > boundary:
                    column_idx = i + 1
                else:
                    break
            
            columns[column_idx].append(block)
        
        # Sort blocks within each column by Y position
        for col_idx in columns:
            columns[col_idx].sort(key=lambda b: (
                b.get("position", {}).get("y0", 0),
                b.get("position", {}).get("x0", 0)
            ))
        
        return dict(columns)
    
    def detect_paragraph_boundaries(self, text_blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Detect paragraph boundaries by analyzing spacing, considering multi-column layouts."""
        if not text_blocks:
            return []
        
        # Detect column boundaries
        column_boundaries = self.detect_column_boundaries(text_blocks)
        
        # Calculate average font size for title detection
        font_sizes = [b.get("font_size", 11.0) for b in text_blocks if b.get("font_size")]
        avg_font_size = sum(font_sizes) / len(font_sizes) if font_sizes else 11.0
        
        # If columns detected, process each column separately
        if column_boundaries:
            columns = self.assign_blocks_to_columns(text_blocks, column_boundaries)
            all_paragraphs = []
            
            # Process each column
            for col_idx in sorted(columns.keys()):
                column_blocks = columns[col_idx]
                column_paragraphs = self._detect_paragraphs_in_column(column_blocks, col_idx, avg_font_size)
                all_paragraphs.extend(column_paragraphs)
            
            # Sort all paragraphs by Y position (top to bottom, left to right)
            all_paragraphs.sort(key=lambda p: (
                p.get("position", {}).get("y0", 0),
                p.get("column", 0)
            ))
            
            return all_paragraphs
        else:
            # No columns detected, process as single column
            return self._detect_paragraphs_in_column(text_blocks, 0, avg_font_size)
    
    def _detect_paragraphs_in_column(self, text_blocks: List[Dict[str, Any]], 
                                     column_idx: int = 0, avg_font_size: float = 11.0) -> List[Dict[str, Any]]:
        """Detect paragraph boundaries within a single column with ML-based chunking."""
        if not text_blocks:
            return []
        
        # Calculate average font size for title detection
        font_sizes = [b.get("font_size", avg_font_size) for b in text_blocks if b.get("font_size")]
        if font_sizes:
            avg_font_size = sum(font_sizes) / len(font_sizes)
        
        # First pass: Calculate typical line spacing and gaps
        gaps = []
        previous_y_end = None
        
        for block in text_blocks:
            y_start = block.get("position", {}).get("y0", 0)
            y_end = block.get("position", {}).get("y1", 0)
            
            if previous_y_end is not None:
                gap = y_start - previous_y_end
                if gap > 0:
                    gaps.append(gap)
            
            previous_y_end = y_end
        
        # Calculate spacing statistics
        if gaps:
            gaps_sorted = sorted(gaps)
            median_gap = gaps_sorted[len(gaps_sorted) // 2]
            avg_gap = sum(gaps) / len(gaps)
            # Use 75th percentile for more robust threshold
            percentile_75 = gaps_sorted[int(len(gaps_sorted) * 0.75)] if len(gaps_sorted) > 4 else median_gap
            
            typical_line_spacing = median_gap
            # Very conservative threshold - only break on very large gaps (real paragraph breaks)
            # Use higher percentile to avoid breaking on normal line spacing
            percentile_90 = gaps_sorted[int(len(gaps_sorted) * 0.90)] if len(gaps_sorted) > 10 else percentile_75
            
            paragraph_break_threshold = max(
                percentile_90 * 1.5,  # Use 90th percentile * 1.5 (very large gaps only)
                typical_line_spacing * 4.0,  # 4x typical spacing (much more conservative)
                avg_gap * 3.0,  # 3x average gap
                25  # Higher minimum threshold
            )
        else:
            paragraph_break_threshold = 30
        
        # Second pass: Group blocks into paragraphs with title/subtitle detection
        paragraphs = []
        current_paragraph = []
        previous_y_end = None
        previous_x_end = None
        
        # Calculate typical_line_spacing for use in loop
        typical_line_spacing = median_gap if gaps else 10.0
        
        for i, block in enumerate(text_blocks):
            y_start = block.get("position", {}).get("y0", 0)
            y_end = block.get("position", {}).get("y1", 0)
            x_start = block.get("position", {}).get("x0", 0)
            x_end = block.get("position", {}).get("x1", 0)
            text = block.get("text", "").strip()
            font_size = block.get("font_size", avg_font_size)
            
            if not text:
                continue
            
            # Check if this should start a new paragraph
            is_new_paragraph = False
            gap = 0
            
            if previous_y_end is not None:
                gap = y_start - previous_y_end
                
                # Primary indicator: Large vertical gap (paragraph spacing)
                # Be more conservative - only break on very large gaps
                if gap > paragraph_break_threshold:
                    is_new_paragraph = True
                
                # Handle text wrapping: if block is significantly to the left (column wrap)
                if not is_new_paragraph and previous_x_end is not None:
                    x_gap = x_start - previous_x_end
                    y_overlap = abs(y_start - previous_y_end) < typical_line_spacing * 2
                    
                    # Only break if moved significantly left AND has substantial gap
                    if x_gap < -80 and y_overlap and gap > typical_line_spacing * 1.5:
                        is_new_paragraph = True
                
                # Check for clear title patterns that should start new paragraph (only for very large gaps)
                if not is_new_paragraph and gap > typical_line_spacing * 3.5:
                    if current_paragraph:
                        prev_text = current_paragraph[-1].get("text", "").strip()
                        # Previous ended with sentence punctuation
                        if prev_text and prev_text[-1] in '.!?':
                            # Check if this block looks like a title
                            title_type = self.detect_title_or_subtitle(text, font_size, avg_font_size, True)
                            if title_type:
                                is_new_paragraph = True
            
            # Start new paragraph if detected
            if is_new_paragraph and current_paragraph:
                para = self._create_paragraph_with_title(current_paragraph, column_idx, gap, avg_font_size)
                if para:  # Only add if paragraph has meaningful content
                    paragraphs.append(para)
                current_paragraph = []
            
            # If current paragraph is getting too large (>3000 chars), consider splitting
            if current_paragraph:
                current_text_length = sum(len(b.get("text", "")) for b in current_paragraph)
                if current_text_length > 3000 and gap > typical_line_spacing * 2:
                    # Split large paragraph at natural break points
                    para = self._create_paragraph_with_title(current_paragraph, column_idx, gap, avg_font_size)
                    if para:
                        paragraphs.append(para)
                    current_paragraph = []
            
            current_paragraph.append(block)
            previous_y_end = y_end
            previous_x_end = x_end
        
        # Add final paragraph
        if current_paragraph:
            para = self._create_paragraph_with_title(current_paragraph, column_idx, 0, avg_font_size)
            if para:  # Only add if paragraph has meaningful content
                paragraphs.append(para)
        
        return paragraphs
    
    def _create_paragraph_with_title(self, blocks: List[Dict[str, Any]], column_idx: int, 
                                     gap_before: float, avg_font_size: float) -> Dict[str, Any]:
        """Create a paragraph structure with title/subtitle detection."""
        if not blocks:
            return {}
        
        # Calculate paragraph boundaries
        para_start = blocks[0].get("position", {}).get("y0", 0)
        para_end = blocks[-1].get("position", {}).get("y1", 0)
        para_x0 = min(b.get("position", {}).get("x0", 0) for b in blocks)
        para_x1 = max(b.get("position", {}).get("x1", 0) for b in blocks)
        
        # Detect title and subtitle from first block(s)
        title = None
        subtitle = None
        content_blocks = blocks.copy()
        
        # Check first block for title
        if len(blocks) > 0:
            first_block = blocks[0]
            first_text = first_block.get("text", "").strip()
            first_font = first_block.get("font_size", avg_font_size)
            
            title_type = self.detect_title_or_subtitle(first_text, first_font, avg_font_size, True)
            if title_type == "title":
                title = first_text
                content_blocks = blocks[1:]  # Remove title from content
            elif title_type == "subtitle":
                subtitle = first_text
                content_blocks = blocks[1:]
        
        # Check second block for subtitle if first was title
        if title and len(blocks) > 1:
            second_block = blocks[1]
            second_text = second_block.get("text", "").strip()
            second_font = second_block.get("font_size", avg_font_size)
            
            subtitle_type = self.detect_title_or_subtitle(second_text, second_font, avg_font_size, True)
            if subtitle_type in ["title", "subtitle"]:
                subtitle = second_text
                content_blocks = blocks[2:]  # Remove subtitle from content
        
        # Build paragraph text (excluding title/subtitle) - clean and combine properly
        paragraph_text_parts = []
        for b in content_blocks:
            block_text = b.get("text", "").strip()
            if block_text:
                # Skip chart labels and metadata at block level
                if self.is_metadata(block_text):
                    continue
                paragraph_text_parts.append(block_text)
        
        if not paragraph_text_parts:
            return None
        
        # Join with spaces and clean
        paragraph_text = " ".join(paragraph_text_parts)
        
        # Fix hyphenated word breaks (e.g., "dif- ferences" -> "differences")
        paragraph_text = re.sub(r'([a-z])-\s+([a-z])', r'\1\2', paragraph_text)
        
        # Fix common word break issues (e.g., "butrich" -> "but rich", "asa" -> "as a")
        paragraph_text = re.sub(r'([a-z]{2,4})([A-Z][a-z]+)', r'\1 \2', paragraph_text)  # "butRich" -> "but Rich"
        paragraph_text = re.sub(r'\b(but|as|is|in|on|at|to|of|for|the|and|or)([a-z]{2,})', r'\1 \2', paragraph_text, flags=re.IGNORECASE)  # "butrich" -> "but rich"
        
        # Clean up multiple spaces
        paragraph_text = re.sub(r'\s+', ' ', paragraph_text).strip()
        
        # Remove metadata patterns
        paragraph_text = re.sub(r'\d+\s+DIW\s+Weekly\s+Report.*?(?=\s+[A-Z])', '', paragraph_text)
        paragraph_text = re.sub(r'\d+/\d{4}', '', paragraph_text)
        paragraph_text = re.sub(r'Figure\s+\d+.*?', '', paragraph_text)
        paragraph_text = re.sub(r'\.(\d+)\s+([A-Z])', r'. \2', paragraph_text)
        paragraph_text = re.sub(r'([a-z])\.(\d+)\s+([A-Z][a-z]+)', r'\1. \3', paragraph_text)
        paragraph_text = re.sub(r'see\s+[^.]{100,}?(available online|online\))\.?', '', paragraph_text, flags=re.IGNORECASE)
        
        # Remove chart labels and axis labels
        paragraph_text = re.sub(r'\b\d+\s+\d+\s+\d+\s+\d+.*?\b', '', paragraph_text)  # "0 60 120 180"
        paragraph_text = re.sub(r'\b[A-Z]{1,4}(\s+[A-Z]{1,4}){2,15}\b', '', paragraph_text)  # Chart abbreviations
        
        # Clean up again
        paragraph_text = re.sub(r'\s+', ' ', paragraph_text).strip()
        
        # Filter out paragraphs that are clearly not content
        if len(paragraph_text) < 50:
            # Check if it's a chart label or metadata
            if re.match(r'^[\d\sA-Z]{0,30}$', paragraph_text):  # Only numbers, spaces, caps
                return None
            if re.match(r'^\d+\s+DIW', paragraph_text):  # Page numbers
                return None
            if len(paragraph_text.split()) < 5:  # Very few words
                return None
        
        # Filter paragraphs that start mid-word (likely extraction error)
        if paragraph_text:
            words = paragraph_text.split()
            if words:
                first_word = words[0].strip().lower()
                # Common word fragments that indicate mid-word start
                word_fragments = ['tion', 'ing', 'ed', 'er', 'ly', 'al', 'ic', 'ous', 'ment', 'ness', 'ity', 'ive', 'able', 'ible']
                # If first word is a known fragment, skip
                if first_word in word_fragments or any(first_word.endswith(frag) for frag in word_fragments):
                    return None
                # If first word is very short (<=3 chars) and lowercase, likely mid-word
                if len(first_word) <= 3 and first_word.isalpha():
                    return None
                # If paragraph starts with lowercase and is short, might be continuation
                if paragraph_text[0].islower() and len(paragraph_text) < 200:
                    # Check if first few words are all lowercase (unlikely start of paragraph)
                    first_three_words = words[:3] if len(words) >= 3 else words
                    if all(w[0].islower() for w in first_three_words if w and w[0].isalpha()):
                        return None
        
        # Filter chart labels and axis labels more aggressively
        if len(paragraph_text) < 150:
            # Check for chart label patterns
            if re.match(r'^[A-Z][a-z]+(\s+[A-Z][a-z]+)*\s+(by|at|in|of)\s+[A-Z]', paragraph_text):
                # Likely a chart title/label
                if len(paragraph_text.split()) <= 8:
                    return None
            # Check for axis labels (numbers or short text)
            if re.match(r'^[\d\sA-Z]{0,40}$', paragraph_text):
                return None
        
        # Only return paragraph if it has meaningful text
        if len(paragraph_text) < 50 and not title:
            return None
        
        return {
            "title": title,
            "subtitle": subtitle,
            "text": paragraph_text,
            "position": {
                "x0": para_x0,
                "x1": para_x1,
                "y0": para_start,
                "y1": para_end,
                "gap_before": gap_before
            },
            "column": column_idx
        }
    
    def cluster_semantically_similar_blocks(self, text_blocks: List[Dict[str, Any]]) -> List[List[int]]:
        """Cluster text blocks by semantic similarity using ML."""
        if not SKLEARN_AVAILABLE or not text_blocks:
            return [[i] for i in range(len(text_blocks))]
        
        # Extract text from blocks
        texts = [block.get("text", "").strip() for block in text_blocks]
        texts = [t for t in texts if t]  # Filter empty
        
        if len(texts) < 2:
            return [[i] for i in range(len(text_blocks))]
        
        try:
            # Vectorize texts
            vectors = self.vectorizer.fit_transform(texts)
            
            # Cluster using DBSCAN
            clustering = DBSCAN(eps=0.3, min_samples=2, metric='cosine')
            labels = clustering.fit_predict(vectors.toarray())
            
            # Group blocks by cluster
            clusters = defaultdict(list)
            for i, label in enumerate(labels):
                if label != -1:  # -1 means noise/outlier
                    clusters[label].append(i)
                else:
                    clusters[i] = [i]  # Each outlier is its own cluster
            
            return list(clusters.values())
        except Exception as e:
            print(f"Warning: ML clustering failed: {e}")
            return [[i] for i in range(len(text_blocks))]


class PDFExtractorV3:
    """Unified PDF extractor with structure, positions, and complete coverage."""
    
    def __init__(self, pdf_path: str, use_ml_boundaries: bool = True):
        self.pdf_path = Path(pdf_path)
        self.fitz_doc = fitz.open(pdf_path)
        self.plumber_doc = pdfplumber.open(pdf_path)
        self.content_items: List[ContentItem] = []
        self.use_ml_boundaries = use_ml_boundaries
        self.ml_detector = MLTextBoundaryDetector(self) if use_ml_boundaries else None
        
    @staticmethod
    def clean_spaces(text: str) -> str:
        """Replace multiple spaces with single space and fix word breaks."""
        if not text:
            return text
        # Fix hyphenated word breaks (e.g., "dif- ferences" -> "differences")
        text = re.sub(r'([a-z])-\s+([a-z])', r'\1\2', text)
        # Fix word breaks where a word is split across lines (e.g., "tion system" -> "tion system" stays, but "dif ferences" -> "differences")
        # Only merge if both parts are short (likely a word break)
        text = re.sub(r'\b([a-z]{1,4})\s+([a-z]{1,4})\b', lambda m: m.group(1) + m.group(2) if len(m.group(1)) + len(m.group(2)) < 8 else m.group(0), text)
        # Replace multiple spaces with single space
        return re.sub(r'\s+', ' ', text).strip()
    
    @staticmethod
    def clean_metadata_from_content(text: str) -> str:
        """Remove footnotes and metadata from content text."""
        if not text:
            return text
        
        # Remove page number patterns
        text = re.sub(r'\d+\s+DIW\s+Weekly\s+Report.*?(?=\s+[A-Z])', '', text)
        text = re.sub(r'\d+/\d{4}', '', text)
        
        # Remove "Figure X" patterns
        text = re.sub(r'Figure\s+\d+.*?', '', text)
        
        # Remove footnote citation patterns
        text = re.sub(r'\.(\d+)\s+([A-Z])', r'. \2', text)
        text = re.sub(r'([a-z])\.(\d+)\s+([A-Z][a-z]+)', r'\1. \3', text)
        
        # Remove standalone footnote numbers
        sentences = re.split(r'([.!?]\s+)', text)
        cleaned_sentences = []
        for sent in sentences:
            if not re.match(r'^\d+\s+[A-Z]', sent.strip()):
                cleaned_sentences.append(sent)
        text = ''.join(cleaned_sentences)
        
        # Remove citation patterns
        text = re.sub(r'see\s+[^.]{100,}?(available online|online\))\.?', '', text, flags=re.IGNORECASE)
        
        # Clean up multiple spaces
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
    
    @staticmethod
    def is_metadata(text: str) -> bool:
        """Check if text is metadata that should be excluded."""
        text = text.strip()
        if len(text) < 2:
            return False
        
        # Chart labels and axis labels (e.g., "0 60 120 180" or "West East City-states")
        if re.match(r'^[\d\s]{5,}$', text):  # Only numbers and spaces
            return True
        if re.match(r'^[A-Z]{1,4}(\s+[A-Z]{1,4}){2,15}$', text):  # Chart abbreviations like "GDP CPI GNP"
            return True
        if re.match(r'^[A-Z][a-z]+\s+[A-Z][a-z]+(\s+[A-Z][a-z]+){0,2}$', text) and len(text) < 50:  # Short label-like text
            # Check if it's likely a chart label (very short, title case)
            words = text.split()
            if len(words) <= 3 and all(w[0].isupper() for w in words):
                return True
        
        metadata_patterns = [
            r'^\d+\s+$',  # Just a number
            r'^(Figure|Table|Box)\s+\d+',
            r'^Source:',
            r'^Note[s]?:',
            r'^©\s+',
            r'^DOI:',
            r'^JEL:',
            r'^Keywords?:',
            r'^ISSN',
            r'^Volume\s+\d+',
            r'^\d+\s+DIW',
            r'^Gross\s+(domestic|value)',  # Chart titles that are too short
            r'^In\s+percent',  # Chart axis labels
        ]
        
        return any(re.match(pattern, text, re.IGNORECASE) for pattern in metadata_patterns)
    
    def is_title(self, text: str, font_size: float, y_position: float, 
                 previous_y: Optional[float] = None, avg_font_size: float = 11.0) -> bool:
        """Heuristic to identify titles based on text characteristics."""
        text = text.strip()
        
        if len(text) < 3:
            return False
        
        # Exclude common non-title patterns
        non_title_patterns = [
            r'^\d+$',
            r'^\d+[.,]\d+',
            r'^[a-z]',
            r'^[^\w]',
            r'.*[.!?]$',
            r'^[A-Z][a-z]+\s+[a-z]+\s+[a-z]',
            r'^In\s+(percent|percentage)',
            r'^At\s+current\s+prices',
            r'^As\s+a\s+percentage',
            r'^[A-Z]{1,4}(\s+[A-Z]{1,4}){1,15}$',
            r'^[A-Z]{1,3}\s*=\s*',
        ]
        
        if any(re.match(pattern, text) for pattern in non_title_patterns):
            return False
        
        # Check title patterns
        title_patterns = [
            r'^[A-Z][A-Z\s]{4,}$',
            r'^\d+\.\s+[A-Z][A-Z]',
            r'^[A-Z][A-Z\s]+[A-Z]$',
            r'^[A-Z][a-z]+(\s+[A-Z][a-z]+)+$',
            r'^[A-Z][a-z]+\s+[a-z]+$',
        ]
        
        is_pattern_match = any(re.match(pattern, text) for pattern in title_patterns)
        is_large_font = font_size > avg_font_size * 1.15
        is_new_line = previous_y is None or abs(y_position - previous_y) > 20
        is_reasonable_length = 3 <= len(text) < 100
        has_title_structure = not re.search(r'\b[a-z]+\s+[a-z]+\b', text)
        
        indicators = sum([
            is_pattern_match,
            is_large_font,
            is_new_line and is_reasonable_length,
            has_title_structure and len(text) < 50
        ])
        
        return indicators >= 3 or (is_pattern_match and is_large_font)
    
    def extract_metadata(self) -> Dict[str, Any]:
        """Extract PDF metadata."""
        metadata = self.fitz_doc.metadata
        return {
            "title": metadata.get("title", ""),
            "author": metadata.get("author", ""),
            "subject": metadata.get("subject", ""),
            "creator": metadata.get("creator", ""),
            "producer": metadata.get("producer", ""),
            "creation_date": metadata.get("creationDate", ""),
            "modification_date": metadata.get("modDate", ""),
            "total_pages": len(self.fitz_doc)
        }
    
    def get_table_regions(self) -> List[Dict[str, Any]]:
        """Get bounding boxes of all tables."""
        table_regions = []
        for page_num, page in enumerate(self.plumber_doc.pages):
            tables = page.find_tables()
            for table in tables:
                bbox = table.bbox
                table_regions.append({
                    "page": page_num + 1,
                    "x0": bbox[0],
                    "y0": bbox[1],
                    "x1": bbox[2],
                    "y1": bbox[3]
                })
        return table_regions
    
    def get_image_regions(self) -> List[Dict[str, Any]]:
        """Get bounding boxes of all images."""
        image_regions = []
        for page_num in range(len(self.fitz_doc)):
            page = self.fitz_doc[page_num]
            image_list = page.get_images()
            for img_index, img in enumerate(image_list):
                xref = img[0]
                try:
                    image_rects = page.get_image_rects(xref)
                    if image_rects:
                        for rect in image_rects:
                            image_regions.append({
                                "page": page_num + 1,
                                "x0": rect.x0,
                                "y0": rect.y0,
                                "x1": rect.x1,
                                "y1": rect.y1,
                                "xref": xref
                            })
                except:
                    continue
        return image_regions
    
    def bbox_overlaps_region(self, bbox: Tuple[float, float, float, float], 
                            region: Dict[str, Any], page: int) -> bool:
        """Check if a bounding box overlaps with a region."""
        if region["page"] != page:
            return False
        x0, y0, x1, y1 = bbox
        if x1 < region["x0"] or x0 > region["x1"] or y1 < region["y0"] or y0 > region["y1"]:
            return False
        
        # Calculate overlap area
        overlap_x0 = max(x0, region["x0"])
        overlap_y0 = max(y0, region["y0"])
        overlap_x1 = min(x1, region["x1"])
        overlap_y1 = min(y1, region["y1"])
        
        overlap_area = (overlap_x1 - overlap_x0) * (overlap_y1 - overlap_y0)
        text_area = (x1 - x0) * (y1 - y0)
        
        return overlap_area > 0.5 * text_area if text_area > 0 else False
    
    def extract_tables(self) -> List[Dict[str, Any]]:
        """Extract all tables with positions and content."""
        tables = []
        for page_num, page in enumerate(self.plumber_doc.pages):
            page_tables = page.extract_tables()  # This returns list of lists
            
            for table_idx, table in enumerate(page_tables):
                if not table:
                    continue
                
                # Get table bounding box from find_tables
                table_objects = page.find_tables()
                bbox = None
                if table_idx < len(table_objects):
                    bbox = table_objects[table_idx].bbox
                else:
                    # Fallback: estimate from page
                    bbox = (0, 0, page.width, page.height)
                
                table_data = []
                for row in table:
                    if row:
                        cleaned_row = []
                        for cell in row:
                            if cell is None:
                                cleaned_row.append("")
                            else:
                                cleaned_row.append(self.clean_spaces(str(cell).strip().replace("\n", " ")))
                        if any(cleaned_row):  # Only add non-empty rows
                            table_data.append(cleaned_row)
                
                if table_data:
                    tables.append({
                        "page": page_num + 1,
                        "table_index": table_idx,
                        "position": {
                            "x0": bbox[0],
                            "y0": bbox[1],
                            "x1": bbox[2],
                            "y1": bbox[3]
                        },
                        "rows": len(table_data),
                        "columns": len(table_data[0]) if table_data else 0,
                        "data": table_data
                    })
        
        return tables
    
    def extract_images(self, table_regions: List[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Extract all images including embedded images and visual content (charts, figures)."""
        images = []
        image_index = 0
        
        # First, extract embedded images
        for page_num in range(len(self.fitz_doc)):
            page = self.fitz_doc[page_num]
            image_list = page.get_images(full=True)
            
            for img in image_list:
                xref = img[0]
                try:
                    base_image = self.fitz_doc.extract_image(xref)
                    image_bytes = base_image["image"]
                    image_ext = base_image["ext"]
                    
                    # Get image position
                    image_rects = page.get_image_rects(xref)
                    bbox = None
                    if image_rects:
                        rect = image_rects[0]
                        bbox = {
                            "x0": rect.x0,
                            "y0": rect.y0,
                            "x1": rect.x1,
                            "y1": rect.y1
                        }
                    
                    # Convert to base64
                    image_base64 = base64.b64encode(image_bytes).decode('utf-8')
                    
                    images.append({
                        "page": page_num + 1,
                        "image_index": image_index,
                        "format": image_ext,
                        "width": base_image["width"],
                        "height": base_image["height"],
                        "position": bbox,
                        "data": image_base64,
                        "type": "embedded"
                    })
                    image_index += 1
                except Exception as e:
                    print(f"Warning: Could not extract embedded image from page {page_num + 1}: {e}")
                    continue
        
        # Now extract visual content (charts, figures) as images
        # These are regions that contain visual elements but aren't text
        if table_regions:
            for page_num in range(len(self.fitz_doc)):
                page = self.fitz_doc[page_num]
                page_tables = [t for t in table_regions if t["page"] == page_num + 1]
                
                # Get all table regions for this page
                for table_region in page_tables:
                    # Check if this is a chart/visual (not a real data table)
                    # by checking if it's detected by pdfplumber but has mostly empty cells
                    plumber_page = self.plumber_doc.pages[page_num]
                    tables = plumber_page.find_tables()
                    
                    # Find matching table
                    matching_table = None
                    for table in tables:
                        if (abs(table.bbox[0] - table_region["x0"]) < 5 and 
                            abs(table.bbox[1] - table_region["y0"]) < 5):
                            matching_table = table
                            break
                    
                    # If it's a chart/visual (has structure but mostly empty), render as image
                    if matching_table:
                        extracted = plumber_page.extract_tables()
                        table_idx = tables.index(matching_table) if matching_table in tables else -1
                        
                        if table_idx >= 0 and table_idx < len(extracted):
                            table_data = extracted[table_idx]
                            # Check if it's mostly empty (likely a chart)
                            total_cells = sum(len(row) for row in table_data) if table_data else 0
                            filled_cells = sum(1 for row in table_data for cell in row if cell and str(cell).strip()) if table_data else 0
                            
                            # If less than 30% filled, treat as visual/chart
                            if total_cells > 0 and (filled_cells / total_cells) < 0.3:
                                try:
                                    # Render the region as an image
                                    bbox = table_region
                                    rect = fitz.Rect(bbox["x0"], bbox["y0"], bbox["x1"], bbox["y1"])
                                    
                                    # Render page region to image
                                    mat = fitz.Matrix(2, 2)  # 2x zoom for better quality
                                    pix = page.get_pixmap(matrix=mat, clip=rect)
                                    img_bytes = pix.tobytes("png")
                                    
                                    # Convert to base64
                                    image_base64 = base64.b64encode(img_bytes).decode('utf-8')
                                    
                                    images.append({
                                        "page": page_num + 1,
                                        "image_index": image_index,
                                        "format": "png",
                                        "width": pix.width,
                                        "height": pix.height,
                                        "position": bbox,
                                        "data": image_base64,
                                        "type": "chart"
                                    })
                                    image_index += 1
                                except Exception as e:
                                    print(f"Warning: Could not render chart region from page {page_num + 1}: {e}")
                                    continue
        
        return images
    
    def extract_text_sections(self, table_regions: List[Dict[str, Any]], 
                             image_regions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract text organized into sections with positions."""
        # First pass: calculate average font size
        font_sizes = []
        for page_num in range(len(self.fitz_doc)):
            page = self.fitz_doc[page_num]
            blocks = page.get_text("dict")["blocks"]
            
            for block in blocks:
                if "lines" not in block:
                    continue
                
                block_bbox = block["bbox"]
                
                # Check if block overlaps with tables or images
                overlaps = False
                for region in table_regions + image_regions:
                    if self.bbox_overlaps_region(block_bbox, region, page_num + 1):
                        overlaps = True
                        break
                
                if overlaps:
                    continue
                
                for line in block["lines"]:
                    for span in line["spans"]:
                        font_sizes.append(span["size"])
        
        avg_font_size = sum(font_sizes) / len(font_sizes) if font_sizes else 11.0
        
        # Second pass: extract text with sections
        sections = []
        current_section = None
        current_text = []
        current_text_blocks = []
        
        previous_y = None
        
        for page_num in range(len(self.fitz_doc)):
            page = self.fitz_doc[page_num]
            blocks = page.get_text("dict")["blocks"]
            
            for block in blocks:
                if "lines" not in block:
                    continue
                
                block_bbox = block["bbox"]
                
                # Check if block overlaps with tables or images
                overlaps = False
                for region in table_regions + image_regions:
                    if self.bbox_overlaps_region(block_bbox, region, page_num + 1):
                        overlaps = True
                        break
                
                if overlaps:
                    continue
                
                for line in block["lines"]:
                    line_text = ""
                    line_font_size = 0
                    line_y = None
                    line_bbox = None
                    
                    for span in line["spans"]:
                        span_text = span["text"]
                        span_font_size = span["size"]
                        span_y = span["bbox"][1]
                        span_bbox = span["bbox"]
                        
                        if line_y is None:
                            line_y = span_y
                            line_bbox = span_bbox
                        if span_font_size > line_font_size:
                            line_font_size = span_font_size
                        
                        line_text += span_text
                    
                    if not line_text.strip():
                        continue
                    
                    # Skip metadata lines
                    if self.is_metadata(line_text):
                        continue
                    
                    # Check if this line is a title
                    is_title_line = self.is_title(line_text, line_font_size, line_y, previous_y, avg_font_size)
                    
                    if is_title_line:
                        # Save previous section
                        if current_section is not None:
                            content = self.clean_spaces(" ".join(current_text).replace("\n", " "))
                            content = self.clean_metadata_from_content(content)
                            
                            # Calculate section position (use first text block)
                            section_bbox = current_text_blocks[0]["position"] if current_text_blocks else None
                            
                            # Apply ML boundary detection - paragraphs are the primary content
                            section_data = {
                                "title": current_section,
                                "page": page_num + 1,
                                "position": section_bbox
                            }
                            
                            # Add ML-detected paragraph boundaries (clean output)
                            if self.use_ml_boundaries and self.ml_detector:
                                # Detect paragraph boundaries with title/subtitle detection
                                paragraphs = self.ml_detector.detect_paragraph_boundaries(current_text_blocks)
                                section_data["paragraphs"] = paragraphs
                                
                                # Mark text boundaries (simplified)
                                if current_text_blocks:
                                    section_data["text_boundaries"] = {
                                        "start": current_text_blocks[0]["position"]["y0"],
                                        "end": current_text_blocks[-1]["position"]["y1"],
                                        "total_paragraphs": len(paragraphs)
                                    }
                            else:
                                # Fallback: create single paragraph from all text
                                if current_text_blocks:
                                    para_text = self.clean_spaces(" ".join([b.get("text", "") for b in current_text_blocks]))
                                    section_data["paragraphs"] = [{
                                        "title": None,
                                        "subtitle": None,
                                        "text": para_text,
                                        "position": section_bbox,
                                        "column": 0,
                                        "block_count": len(current_text_blocks)
                                    }]
                            
                            sections.append(section_data)
                        
                        # Start new section
                        current_section = self.clean_spaces(line_text.strip().replace("\n", " "))
                        current_text = []
                        current_text_blocks = []
                    else:
                        if current_section is None:
                            current_section = "Introduction"
                        
                        # Clean the line text
                        cleaned_line = self.clean_spaces(line_text.replace("\n", " "))
                        
                        # Skip if it's metadata or chart labels
                        if self.is_metadata(cleaned_line):
                            continue
                        
                        # Skip very short lines that look like chart labels
                        if len(cleaned_line) < 10 and re.match(r'^[\d\sA-Z]{0,20}$', cleaned_line):
                            continue
                        
                        current_text.append(cleaned_line)
                        
                        # Store text block with position
                        if line_bbox:
                            current_text_blocks.append({
                                "text": cleaned_line,
                                "position": {
                                    "x0": line_bbox[0],
                                    "y0": line_bbox[1],
                                    "x1": line_bbox[2],
                                    "y1": line_bbox[3]
                                },
                                "font_size": line_font_size
                            })
                    
                    previous_y = line_y
        
        # Add final section
        if current_section is not None:
            content = " ".join(current_text).replace("\n", " ").strip()
            content = self.clean_metadata_from_content(content)
            section_bbox = current_text_blocks[0]["position"] if current_text_blocks else None
            
            section_data = {
                "title": current_section,
                "page": len(self.fitz_doc),
                "position": section_bbox
            }
            
            # Apply ML boundary detection - paragraphs are the primary content
            if self.use_ml_boundaries and self.ml_detector:
                # Detect paragraph boundaries with title/subtitle detection
                paragraphs = self.ml_detector.detect_paragraph_boundaries(current_text_blocks)
                section_data["paragraphs"] = paragraphs
                
                # Mark text boundaries (simplified)
                if current_text_blocks:
                    section_data["text_boundaries"] = {
                        "start": current_text_blocks[0]["position"]["y0"],
                        "end": current_text_blocks[-1]["position"]["y1"],
                        "total_paragraphs": len(paragraphs)
                    }
            else:
                # Fallback: create single paragraph from all text
                if current_text_blocks:
                    para_text = self.clean_spaces(" ".join([b.get("text", "") for b in current_text_blocks]))
                    section_data["paragraphs"] = [{
                        "title": None,
                        "subtitle": None,
                        "text": para_text,
                        "position": section_bbox,
                        "column": 0,
                        "block_count": len(current_text_blocks)
                    }]
            
            sections.append(section_data)
        
        return sections
    
    def build_unified_content(self, sections: List[Dict[str, Any]], 
                             tables: List[Dict[str, Any]], 
                             images: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Build unified content array sorted by document flow (page, then y-position)."""
        content_items = []
        
        # Add sections
        for section in sections:
            content_items.append(ContentItem(
                type="section",
                page=section["page"],
                y_position=section["position"]["y0"] if section["position"] else 0,
                data=section
            ))
        
        # Add tables
        for table in tables:
            content_items.append(ContentItem(
                type="table",
                page=table["page"],
                y_position=table["position"]["y0"],
                data=table
            ))
        
        # Add images
        for image in images:
            if image["position"]:
                content_items.append(ContentItem(
                    type="image",
                    page=image["page"],
                    y_position=image["position"]["y0"],
                    data=image
                ))
        
        # Sort by page, then by y-position (top to bottom)
        content_items.sort(key=lambda x: (x.page, x.y_position))
        
        # Convert to dict format
        unified_content = []
        for item in content_items:
            unified_content.append({
                "type": item.type,
                "page": item.page,
                "position": item.data.get("position"),
                **item.data
            })
        
        return unified_content
    
    def extract_all(self) -> Dict[str, Any]:
        """Extract all content with unified structure."""
        print("Extracting metadata...")
        metadata = self.extract_metadata()
        
        print("Extracting tables...")
        tables = self.extract_tables()
        table_regions = self.get_table_regions()
        
        print("Extracting images/charts...")
        images = self.extract_images(table_regions)
        image_regions = self.get_image_regions()
        
        print("Extracting text sections (excluding tables and images)...")
        sections = self.extract_text_sections(table_regions, image_regions)
        
        print("Building unified content structure...")
        unified_content = self.build_unified_content(sections, tables, images)
        
        # Calculate ML statistics (simplified)
        ml_stats = {}
        if self.use_ml_boundaries:
            total_paragraphs = sum(len(s.get("paragraphs", [])) for s in sections)
            paragraphs_with_titles = sum(1 for s in sections for p in s.get("paragraphs", []) if p.get("title"))
            paragraphs_with_subtitles = sum(1 for s in sections for p in s.get("paragraphs", []) if p.get("subtitle"))
            
            ml_stats = {
                "ml_enabled": True,
                "total_paragraphs_detected": total_paragraphs,
                "paragraphs_with_titles": paragraphs_with_titles,
                "paragraphs_with_subtitles": paragraphs_with_subtitles
            }
        else:
            ml_stats = {"ml_enabled": False}
        
        # Restructure output: sections are primary, with paragraphs as main content
        restructured_sections = []
        for section in sections:
            # Each section contains its paragraphs as primary content
            section_data = {
                "title": section.get("title"),
                "page": section.get("page"),
                "position": section.get("position"),
                "paragraphs": section.get("paragraphs", [])
            }
            # Add text_boundaries if available
            if "text_boundaries" in section:
                section_data["text_boundaries"] = section["text_boundaries"]
            restructured_sections.append(section_data)
        
        result = {
            "pdf_file": str(self.pdf_path.name),
            "metadata": metadata,
            "sections": restructured_sections,  # Primary structure: sections with paragraphs
            "tables": tables,
            "images": images,
            "summary": {
                "total_pages": len(self.fitz_doc),
                "total_sections": len(sections),
                "total_tables": len(tables),
                "total_images": len(images),
                **ml_stats
            }
        }
        
        return result
    
    def close(self):
        """Close PDF documents."""
        self.fitz_doc.close()
        self.plumber_doc.close()


def main():
    """Main function to run the V3 PDF extractor."""
    pdf_path = Path(__file__).parent / "dwr-25-40-1.pdf"
    
    if not pdf_path.exists():
        print(f"Error: PDF file not found at {pdf_path}")
        return
    
    print(f"Processing PDF (V3 UNIFIED EXTRACTION WITH ML): {pdf_path}")
    extractor = PDFExtractorV3(str(pdf_path), use_ml_boundaries=True)
    
    try:
        result = extractor.extract_all()
        
        # Save to JSON
        output_path = pdf_path.parent / "extracted_content_v3.json"
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        print(f"\nV3 Extraction complete!")
        print(f"  - Pages: {result['summary']['total_pages']}")
        print(f"  - Sections: {result['summary']['total_sections']}")
        print(f"  - Tables: {result['summary']['total_tables']}")
        print(f"  - Images: {result['summary']['total_images']}")
        if 'total_paragraphs_detected' in result['summary']:
            print(f"  - Paragraphs: {result['summary']['total_paragraphs_detected']}")
        print(f"\nOutput saved to: {output_path}")
        
    finally:
        extractor.close()


if __name__ == "__main__":
    main()

