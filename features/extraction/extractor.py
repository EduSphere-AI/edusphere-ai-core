"""
Main PDF extractor orchestrator.
Coordinates all extraction modules and generates standardized JSON output.
"""

import fitz  # PyMuPDF
import json
import os
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

from .table_extractor import extract_tables
from .chart_extractor import extract_charts
from .image_extractor import extract_images
from .text_extractor import extract_text, TextCategorizer
from .utils import get_bounding_box


class PDFExtractor:
    """
    Main class for extracting content from academic PDFs.
    """
    
    def __init__(self):
        """Initialize the PDF extractor."""
        self.categorizer = TextCategorizer()
    
    def extract(self, pdf_path: str, output_path: Optional[str] = None) -> Dict:
        """
        Extract all content from a PDF file.
        
        Args:
            pdf_path: Path to the input PDF file
            output_path: Optional path for output JSON file. If None, generates
                        output path based on input filename.
        
        Returns:
            Dictionary containing extracted content in standardized format
        """
        # Validate input file
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
        
        # Open PDF
        doc = fitz.open(pdf_path)
        
        # Generate document ID from filename
        doc_id = Path(pdf_path).stem
        
        # Process each page
        pages_data = []
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            page_data = self._extract_page_content(page, page_num + 1)
            pages_data.append(page_data)
        
        doc.close()
        
        # Build output structure
        output = {
            "document_id": doc_id,
            "source_file": os.path.basename(pdf_path),
            "extraction_date": datetime.now().isoformat(),
            "total_pages": len(pages_data),
            "pages": pages_data
        }
        
        # Save to JSON if output path provided
        if output_path is None:
            output_path = os.path.join(
                os.path.dirname(pdf_path),
                f"{doc_id}_extracted.json"
            )
        
        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        
        return output
    
    def _extract_page_content(self, page: fitz.Page, page_number: int) -> Dict:
        """
        Extract all content from a single page.
        
        Args:
            page: PyMuPDF Page object
            page_number: Page number (1-indexed)
        
        Returns:
            Dictionary with extracted content for the page
        """
        # Extract tables
        tables = extract_tables(page)
        table_regions = [table["bbox"] for table in tables]
        
        # Extract charts
        charts = extract_charts(page)
        chart_regions = [chart["bbox"] for chart in charts]
        
        # Extract images
        images = extract_images(page)
        image_regions = [image["bbox"] for image in images]
        
        # Extract text (excluding text in tables, charts, and images)
        text_content = extract_text(
            page,
            table_regions,
            chart_regions,
            image_regions,
            categorizer=self.categorizer
        )
        
        # Build page data structure
        page_data = {
            "page_number": page_number,
            "tables": self._format_tables(tables),
            "charts": self._format_charts(charts),
            "images": self._format_images(images),
            "text": self._format_text(text_content)
        }
        
        return page_data
    
    def _format_tables(self, tables: List[Dict]) -> List[Dict]:
        """Format table data for JSON output."""
        formatted = []
        for table in tables:
            formatted.append({
                "table_id": table["table_id"],
                "bbox": table["bbox"],
                "num_rows": table["num_rows"],
                "num_cols": table["num_cols"],
                "structure": table["structure"],
                "validation": table["validation"]
            })
        return formatted
    
    def _format_charts(self, charts: List[Dict]) -> List[Dict]:
        """Format chart data for JSON output."""
        formatted = []
        for chart in charts:
            formatted.append({
                "figure_id": chart["figure_id"],
                "bbox": chart["bbox"],
                "title": chart["title"],
                "axis_labels": chart["axis_labels"],
                "legend": chart["legend"],
                "data_labels": chart["data_labels"],
                "internal_text": chart["internal_text"],
                "caption": chart["caption"],
                "figure_number": chart["figure_number"]
            })
        return formatted
    
    def _format_images(self, images: List[Dict]) -> List[Dict]:
        """Format image data for JSON output."""
        formatted = []
        for image in images:
            formatted.append({
                "image_id": image["image_id"],
                "bbox": image["bbox"],
                "width": image["width"],
                "height": image["height"],
                "colorspace": image["colorspace"],
                "ext": image["ext"],
                "size_bytes": image["size"],
                "embedded_text": image["embedded_text"],
                "label": image["label"],
                "figure_id": image["figure_id"],
                "figure_number": image["figure_number"]
            })
        return formatted
    
    def _format_text(self, text_content: Dict) -> Dict:
        """Format text content for JSON output."""
        formatted = {
            "titles": [self._format_text_block(t) for t in text_content["titles"]],
            "subtitles": [self._format_text_block(t) for t in text_content["subtitles"]],
            "body": [self._format_text_block(t) for t in text_content["body"]],
            "citations": [self._format_text_block(t) for t in text_content["citations"]]
        }
        return formatted
    
    def _format_text_block(self, text_block: Dict) -> Dict:
        """Format a single text block for JSON output."""
        return {
            "text": text_block["text"],
            "bbox": text_block["bbox"],
            "font_size": text_block["font"]["size"],
            "is_bold": text_block["font"]["is_bold"],
            "is_italic": text_block["font"]["is_italic"],
            "font_name": text_block["font"]["font"]
        }

