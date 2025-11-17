"""
Utility functions for PDF content extraction.
Includes layout detection, bounding box operations, and font analysis.
"""

import fitz  # PyMuPDF
import numpy as np
from typing import List, Tuple, Dict, Optional


def get_bounding_box(rect: fitz.Rect) -> Dict[str, float]:
    """Convert PyMuPDF Rect to dictionary format."""
    return {
        "x0": rect.x0,
        "y0": rect.y0,
        "x1": rect.x1,
        "y1": rect.y1,
        "width": rect.width,
        "height": rect.height
    }


def boxes_intersect(box1: Dict[str, float], box2: Dict[str, float], 
                   threshold: float = 0.1) -> bool:
    """
    Check if two bounding boxes intersect.
    threshold: minimum overlap ratio to consider as intersection.
    """
    # Calculate intersection
    x0 = max(box1["x0"], box2["x0"])
    y0 = max(box1["y0"], box2["y0"])
    x1 = min(box1["x1"], box2["x1"])
    y1 = min(box1["y1"], box2["y1"])
    
    if x1 <= x0 or y1 <= y0:
        return False
    
    # Calculate intersection area
    intersection_area = (x1 - x0) * (y1 - y0)
    box1_area = box1["width"] * box1["height"]
    box2_area = box2["width"] * box2["height"]
    
    # Check if intersection exceeds threshold
    overlap_ratio = intersection_area / min(box1_area, box2_area)
    return overlap_ratio >= threshold


def text_in_box(text_bbox: Dict[str, float], container_bbox: Dict[str, float],
                threshold: float = 0.5) -> bool:
    """
    Check if a text bounding box is contained within a container box.
    threshold: minimum overlap ratio to consider text as inside container.
    """
    return boxes_intersect(text_bbox, container_bbox, threshold)


def detect_rectangular_regions(page: fitz.Page, min_width: float = 50, 
                               min_height: float = 50) -> List[Dict[str, float]]:
    """
    Detect rectangular regions on a page that might be tables or structured content.
    Uses drawing operations and text alignment patterns.
    """
    regions = []
    
    # Get drawing operations (lines, rectangles)
    drawings = page.get_drawings()
    
    # Group lines that form rectangles
    horizontal_lines = []
    vertical_lines = []
    
    for drawing in drawings:
        if drawing["type"] == "l":  # line
            items = drawing["items"]
            for item in items:
                if item[0] == "l":  # line item
                    x0, y0, x1, y1 = item[1:]
                    # Classify as horizontal or vertical
                    if abs(y1 - y0) < 5:  # horizontal line
                        horizontal_lines.append((min(x0, x1), max(x0, x1), y0))
                    elif abs(x1 - x0) < 5:  # vertical line
                        vertical_lines.append((min(y0, y1), max(y0, y1), x0))
    
    # Find intersections to form rectangles
    # Simple heuristic: look for horizontal lines with similar y-coordinates
    # and vertical lines with similar x-coordinates
    h_groups = {}
    for x0, x1, y in horizontal_lines:
        key = round(y / 5) * 5  # Group by approximate y position
        if key not in h_groups:
            h_groups[key] = []
        h_groups[key].append((x0, x1))
    
    v_groups = {}
    for y0, y1, x in vertical_lines:
        key = round(x / 5) * 5  # Group by approximate x position
        if key not in v_groups:
            v_groups[key] = []
        v_groups[key].append((y0, y1))
    
    # Form rectangular regions from line intersections
    for y, h_lines in h_groups.items():
        for x, v_lines in v_groups.items():
            # Check if lines form a rectangle
            h_span = [min([l[0] for l in h_lines]), max([l[1] for l in h_lines])]
            v_span = [min([l[0] for l in v_lines]), max([l[1] for l in v_lines])]
            
            width = h_span[1] - h_span[0]
            height = v_span[1] - v_span[0]
            
            if width >= min_width and height >= min_height:
                regions.append({
                    "x0": h_span[0],
                    "y0": v_span[0],
                    "x1": h_span[1],
                    "y1": v_span[1],
                    "width": width,
                    "height": height
                })
    
    return regions


def analyze_font_properties(text_dict: Dict) -> Dict[str, any]:
    """
    Extract font properties from a text dictionary.
    """
    font_info = {
        "size": text_dict.get("size", 0),
        "flags": text_dict.get("flags", 0),
        "font": text_dict.get("font", ""),
        "is_bold": bool(text_dict.get("flags", 0) & 16),  # Bit 4 = bold
        "is_italic": bool(text_dict.get("flags", 0) & 1),  # Bit 0 = italic
    }
    return font_info


def get_text_alignment(text_blocks: List[Dict], page_width: float) -> str:
    """
    Determine text alignment (left, center, right) based on text positions.
    """
    if not text_blocks:
        return "left"
    
    x0_positions = [block["bbox"]["x0"] for block in text_blocks]
    avg_x0 = np.mean(x0_positions)
    
    # Heuristic: if average x0 is near left margin, it's left-aligned
    # If near center, it's center-aligned, etc.
    left_margin = page_width * 0.1
    center = page_width * 0.5
    
    if avg_x0 < left_margin + 20:
        return "left"
    elif abs(avg_x0 - center) < 50:
        return "center"
    else:
        return "right"


def extract_text_with_positions(page: fitz.Page) -> List[Dict]:
    """
    Extract text with detailed position and font information.
    Returns list of text dictionaries with bbox, text, and font properties.
    """
    text_blocks = []
    
    # Get text as dict for detailed information
    text_dict = page.get_text("dict")
    
    for block in text_dict.get("blocks", []):
        if block.get("type") == 0:  # Text block
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    bbox = span.get("bbox", [0, 0, 0, 0])
                    text_blocks.append({
                        "text": span.get("text", ""),
                        "bbox": {
                            "x0": bbox[0],
                            "y0": bbox[1],
                            "x1": bbox[2],
                            "y1": bbox[3],
                            "width": bbox[2] - bbox[0],
                            "height": bbox[3] - bbox[1]
                        },
                        "font": analyze_font_properties(span),
                        "block_num": block.get("number", -1)
                    })
    
    return text_blocks

