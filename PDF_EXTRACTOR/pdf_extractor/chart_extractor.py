"""
Chart extraction module using Option A: Geometry + Text Parsing.
Extracts vector-based charts and their contextual information.
"""

import fitz  # PyMuPDF
import numpy as np
import re
from typing import List, Dict, Optional, Tuple
from .utils import get_bounding_box, boxes_intersect, extract_text_with_positions


def detect_chart_regions(page: fitz.Page) -> List[Dict[str, float]]:
    """
    Detect chart regions by identifying dense vector path clusters,
    axis lines, and grid patterns.
    """
    regions = []
    
    # Get all drawing operations
    drawings = page.get_drawings()
    
    # Collect paths and lines that might form charts
    paths = []
    lines = []
    
    for drawing in drawings:
        if drawing["type"] == "l":  # line
            items = drawing["items"]
            for item in items:
                if item[0] == "l":  # line
                    lines.append(item[1:])
                elif item[0] == "c":  # curve
                    paths.append(item[1:])
    
    # Look for patterns typical of charts:
    # 1. Multiple parallel lines (grid)
    # 2. Perpendicular line intersections (axes)
    # 3. Dense path clusters
    
    # Find axis-like lines (long lines that intersect)
    axis_candidates = []
    for line in lines:
        x0, y0, x1, y1 = line
        length = np.sqrt((x1 - x0)**2 + (y1 - y0)**2)
        if length > 50:  # Significant length
            axis_candidates.append({
                "line": line,
                "length": length,
                "is_horizontal": abs(y1 - y0) < 5,
                "is_vertical": abs(x1 - x0) < 5
            })
    
    # Find intersections to form chart bounding boxes
    for i, axis1 in enumerate(axis_candidates):
        for axis2 in axis_candidates[i+1:]:
            # Check if lines are perpendicular
            if (axis1["is_horizontal"] and axis2["is_vertical"]) or \
               (axis1["is_vertical"] and axis2["is_horizontal"]):
                
                # Find intersection point
                line1 = axis1["line"]
                line2 = axis2["line"]
                
                # Simple intersection check
                if axis1["is_horizontal"]:
                    h_line = line1
                    v_line = line2
                else:
                    h_line = line2
                    v_line = line1
                
                # Get bounding box around intersection area
                x_min = min(h_line[0], h_line[2], v_line[0], v_line[2])
                x_max = max(h_line[0], h_line[2], v_line[0], v_line[2])
                y_min = min(h_line[1], h_line[3], v_line[1], v_line[3])
                y_max = max(h_line[1], h_line[3], v_line[1], v_line[3])
                
                # Expand to include nearby paths and text
                expansion = 50
                region = {
                    "x0": max(0, x_min - expansion),
                    "y0": max(0, y_min - expansion),
                    "x1": x_max + expansion,
                    "y1": y_max + expansion,
                    "width": (x_max + expansion) - max(0, x_min - expansion),
                    "height": (y_max + expansion) - max(0, y_min - expansion)
                }
                
                # Check if region has sufficient content
                if region["width"] > 100 and region["height"] > 100:
                    regions.append(region)
    
    # Also look for dense path clusters (curves, polygons)
    if paths:
        path_points = []
        for path in paths:
            # Extract points from path (simplified)
            if len(path) >= 4:
                path_points.extend([(path[0], path[1]), (path[-2], path[-1])])
        
        if len(path_points) >= 4:
            # Cluster path points
            x_coords = [p[0] for p in path_points]
            y_coords = [p[1] for p in path_points]
            
            x_min, x_max = min(x_coords), max(x_coords)
            y_min, y_max = min(y_coords), max(y_coords)
            
            if (x_max - x_min) > 50 and (y_max - y_min) > 50:
                regions.append({
                    "x0": x_min - 20,
                    "y0": y_min - 20,
                    "x1": x_max + 20,
                    "y1": y_max + 20,
                    "width": (x_max + 20) - (x_min - 20),
                    "height": (y_max + 20) - (y_min - 20)
                })
    
    # Remove overlapping regions
    regions = _remove_overlapping_regions(regions)
    
    return regions


def _remove_overlapping_regions(regions: List[Dict[str, float]], 
                                overlap_threshold: float = 0.3) -> List[Dict[str, float]]:
    """Remove overlapping regions, keeping larger ones."""
    if not regions:
        return []
    
    regions_sorted = sorted(regions, 
                           key=lambda r: r["width"] * r["height"], 
                           reverse=True)
    
    filtered = []
    for region in regions_sorted:
        is_overlapping = False
        for existing in filtered:
            if boxes_intersect(region, existing, overlap_threshold):
                is_overlapping = True
                break
        if not is_overlapping:
            filtered.append(region)
    
    return filtered


def extract_chart_components(page: fitz.Page, chart_region: Dict[str, float]) -> Dict:
    """
    Extract chart components: axis labels, titles, legends, and data points.
    """
    text_blocks = extract_text_with_positions(page)
    
    # Find text within or near the chart region
    chart_texts = []
    nearby_texts = []
    
    for block in text_blocks:
        block_center_x = (block["bbox"]["x0"] + block["bbox"]["x1"]) / 2
        block_center_y = (block["bbox"]["y0"] + block["bbox"]["y1"]) / 2
        
        # Check if text is inside chart region
        if (chart_region["x0"] <= block_center_x <= chart_region["x1"] and
            chart_region["y0"] <= block_center_y <= chart_region["y1"]):
            chart_texts.append(block)
        # Check if text is nearby (within 30 pixels)
        elif (abs(block_center_x - chart_region["x0"]) < 30 or
              abs(block_center_x - chart_region["x1"]) < 30 or
              abs(block_center_y - chart_region["y0"]) < 30 or
              abs(block_center_y - chart_region["y1"]) < 30):
            nearby_texts.append(block)
    
    # Categorize chart text
    axis_labels = []
    title = None
    legend_items = []
    data_labels = []
    
    # Heuristics for categorization:
    # - Title: Usually above chart, larger font, centered
    # - Axis labels: Near edges of chart region
    # - Legend: Usually in corner, smaller font, may have symbols
    # - Data labels: Small text, near chart center
    
    chart_center_x = (chart_region["x0"] + chart_region["x1"]) / 2
    chart_center_y = (chart_region["y0"] + chart_region["y1"]) / 2
    
    for text in chart_texts:
        text_center_x = (text["bbox"]["x0"] + text["bbox"]["x1"]) / 2
        text_center_y = (text["bbox"]["y0"] + text["bbox"]["y1"]) / 2
        
        font_size = text["font"]["size"]
        
        # Title: large font, above center, or centered horizontally
        if font_size > 10 and (text_center_y < chart_center_y - 20 or
                               abs(text_center_x - chart_center_x) < 30):
            if title is None or font_size > title["font"]["size"]:
                title = text
        
        # Axis labels: near edges
        elif (abs(text_center_x - chart_region["x0"]) < 20 or
              abs(text_center_x - chart_region["x1"]) < 20 or
              abs(text_center_y - chart_region["y0"]) < 20 or
              abs(text_center_y - chart_region["y1"]) < 20):
            axis_labels.append(text)
        
        # Data labels: small text, near center
        elif font_size < 9 and abs(text_center_x - chart_center_x) < chart_region["width"] * 0.4:
            data_labels.append(text)
        
        # Legend: usually in corner
        else:
            legend_items.append(text)
    
    return {
        "title": title["text"] if title else None,
        "axis_labels": [t["text"] for t in axis_labels],
        "legend": [t["text"] for t in legend_items],
        "data_labels": [t["text"] for t in data_labels],
        "internal_text": [t["text"] for t in chart_texts]
    }


def find_chart_caption(page: fitz.Page, chart_region: Dict[str, float]) -> Optional[Dict]:
    """
    Find caption text associated with the chart (e.g., "Figure 1", "Fig. 2").
    """
    text_blocks = extract_text_with_positions(page)
    
    # Look for text below or near the chart with figure keywords
    figure_patterns = [
        r'[Ff]igure\s+\d+',
        r'[Ff]ig\.\s*\d+',
        r'[Ff]ig\s+\d+',
        r'[Gg]raph\s+\d+',
        r'[Cc]hart\s+\d+'
    ]
    
    # Search in text below the chart (within 100 pixels)
    search_y_start = chart_region["y1"]
    search_y_end = chart_region["y1"] + 100
    
    for block in text_blocks:
        block_y = (block["bbox"]["y0"] + block["bbox"]["y1"]) / 2
        
        if search_y_start <= block_y <= search_y_end:
            text = block["text"]
            for pattern in figure_patterns:
                if re.search(pattern, text):
                    # Extract figure number
                    match = re.search(r'\d+', text)
                    figure_num = match.group() if match else None
                    
                    return {
                        "caption_text": text,
                        "figure_id": f"figure_{figure_num}" if figure_num else None,
                        "figure_number": figure_num,
                        "bbox": block["bbox"]
                    }
    
    return None


def extract_charts(page: fitz.Page) -> List[Dict]:
    """
    Main function to extract all charts from a page.
    Returns list of chart dictionaries with geometry and contextual information.
    """
    charts = []
    
    # Detect chart regions
    chart_regions = detect_chart_regions(page)
    
    for idx, region in enumerate(chart_regions):
        # Extract chart components
        components = extract_chart_components(page, region)
        
        # Find associated caption
        caption = find_chart_caption(page, region)
        
        # Generate figure ID
        if caption and caption.get("figure_id"):
            figure_id = caption["figure_id"]
        else:
            figure_id = f"chart_{idx + 1}"
        
        chart_data = {
            "figure_id": figure_id,
            "bbox": region,
            "title": components["title"],
            "axis_labels": components["axis_labels"],
            "legend": components["legend"],
            "data_labels": components["data_labels"],
            "internal_text": components["internal_text"],
            "caption": caption["caption_text"] if caption else None,
            "figure_number": caption["figure_number"] if caption else None
        }
        
        charts.append(chart_data)
    
    return charts

