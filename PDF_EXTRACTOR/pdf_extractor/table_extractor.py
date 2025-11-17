"""
Table extraction module.
Detects and extracts tables using vector-based layout detection without OCR.
"""

import fitz  # PyMuPDF
import numpy as np
from typing import List, Dict, Optional, Tuple
from .utils import get_bounding_box, boxes_intersect, extract_text_with_positions


def detect_table_regions(page: fitz.Page) -> List[Dict[str, float]]:
    """
    Detect potential table regions on a page using vector-based layout analysis.
    """
    regions = []
    
    # Get all drawing operations (lines, rectangles)
    drawings = page.get_drawings()
    
    # Collect horizontal and vertical lines
    horizontal_lines = []
    vertical_lines = []
    
    for drawing in drawings:
        if drawing["type"] == "l":  # line
            items = drawing["items"]
            for item in items:
                if item[0] == "l":  # line item
                    x0, y0, x1, y1 = item[1:]
                    # Classify as horizontal or vertical (with tolerance)
                    if abs(y1 - y0) < 3 and abs(x1 - x0) > 10:  # horizontal line
                        horizontal_lines.append((min(x0, x1), max(x0, x1), y0))
                    elif abs(x1 - x0) < 3 and abs(y1 - y0) > 10:  # vertical line
                        vertical_lines.append((min(y0, y1), max(y0, y1), x0))
    
    # Group lines by proximity to form grid structures
    # Find horizontal line clusters
    h_clusters = _cluster_lines(horizontal_lines, axis=1, threshold=5)
    v_clusters = _cluster_lines(vertical_lines, axis=0, threshold=5)
    
    # Form rectangular regions from line intersections
    for h_cluster in h_clusters:
        for v_cluster in v_clusters:
            # Get bounding box of intersection
            h_min_x = min([line[0] for line in h_cluster])
            h_max_x = max([line[1] for line in h_cluster])
            h_y = np.mean([line[2] for line in h_cluster])
            
            v_min_y = min([line[0] for line in v_cluster])
            v_max_y = max([line[1] for line in v_cluster])
            v_x = np.mean([line[2] for line in v_cluster])
            
            # Check if this forms a valid table region
            width = h_max_x - h_min_x
            height = v_max_y - v_min_y
            
            if width > 50 and height > 50:
                # Find all horizontal lines in this region
                h_lines_in_region = [l for l in horizontal_lines 
                                    if h_min_x <= l[0] <= h_max_x and 
                                    v_min_y <= l[2] <= v_max_y]
                v_lines_in_region = [l for l in vertical_lines 
                                    if v_min_y <= l[0] <= v_max_y and 
                                    h_min_x <= l[2] <= h_max_x]
                
                # If we have multiple lines forming a grid, it's likely a table
                if len(h_lines_in_region) >= 2 and len(v_lines_in_region) >= 2:
                    regions.append({
                        "x0": h_min_x,
                        "y0": v_min_y,
                        "x1": h_max_x,
                        "y1": v_max_y,
                        "width": width,
                        "height": height
                    })
    
    # Also check for text-based table patterns (aligned columns)
    text_tables = _detect_text_based_tables(page)
    regions.extend(text_tables)
    
    # Remove overlapping regions
    regions = _remove_overlapping_regions(regions)
    
    return regions


def _cluster_lines(lines: List[Tuple], axis: int, threshold: float) -> List[List[Tuple]]:
    """
    Cluster lines that are close together.
    axis: 0 for vertical (cluster by x), 1 for horizontal (cluster by y)
    """
    if not lines:
        return []
    
    clusters = []
    used = set()
    
    for i, line in enumerate(lines):
        if i in used:
            continue
        
        cluster = [line]
        used.add(i)
        
        # Find nearby lines
        if axis == 1:  # horizontal lines, cluster by y
            ref_pos = line[2]  # y position
            for j, other_line in enumerate(lines):
                if j not in used and abs(other_line[2] - ref_pos) < threshold:
                    cluster.append(other_line)
                    used.add(j)
        else:  # vertical lines, cluster by x
            ref_pos = line[2]  # x position
            for j, other_line in enumerate(lines):
                if j not in used and abs(other_line[2] - ref_pos) < threshold:
                    cluster.append(other_line)
                    used.add(j)
        
        clusters.append(cluster)
    
    return clusters


def _detect_text_based_tables(page: fitz.Page) -> List[Dict[str, float]]:
    """
    Detect tables based on text alignment patterns (columns of aligned text).
    """
    text_blocks = extract_text_with_positions(page)
    
    if len(text_blocks) < 4:  # Need at least a few text blocks
        return []
    
    # Group text by approximate x-position (columns)
    x_positions = [block["bbox"]["x0"] for block in text_blocks]
    
    # Cluster x-positions to find columns
    x_clusters = []
    sorted_x = sorted(set([round(x / 10) * 10 for x in x_positions]))
    
    current_cluster = [sorted_x[0]]
    for x in sorted_x[1:]:
        if x - current_cluster[-1] < 20:  # Close enough to be same column
            current_cluster.append(x)
        else:
            if len(current_cluster) >= 3:  # At least 3 items in column
                x_clusters.append(current_cluster)
            current_cluster = [x]
    
    if len(current_cluster) >= 3:
        x_clusters.append(current_cluster)
    
    # If we have multiple columns with multiple rows, it might be a table
    regions = []
    if len(x_clusters) >= 2:  # At least 2 columns
        # Find bounding box of all text in these columns
        column_texts = []
        for cluster in x_clusters:
            cluster_center = np.mean(cluster)
            for block in text_blocks:
                if abs(block["bbox"]["x0"] - cluster_center) < 30:
                    column_texts.append(block)
        
        if len(column_texts) >= 6:  # At least 6 text blocks
            x0 = min([b["bbox"]["x0"] for b in column_texts])
            y0 = min([b["bbox"]["y0"] for b in column_texts])
            x1 = max([b["bbox"]["x1"] for b in column_texts])
            y1 = max([b["bbox"]["y1"] for b in column_texts])
            
            regions.append({
                "x0": x0,
                "y0": y0,
                "x1": x1,
                "y1": y1,
                "width": x1 - x0,
                "height": y1 - y0
            })
    
    return regions


def _remove_overlapping_regions(regions: List[Dict[str, float]], 
                                overlap_threshold: float = 0.5) -> List[Dict[str, float]]:
    """Remove overlapping regions, keeping the larger one."""
    if not regions:
        return []
    
    # Sort by area (largest first)
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


def reconstruct_table_structure(page: fitz.Page, table_region: Dict[str, float]) -> Optional[Dict]:
    """
    Reconstruct table structure (rows and columns) from text positions.
    """
    text_blocks = extract_text_with_positions(page)
    
    # Filter text blocks that are within the table region
    table_texts = []
    for block in text_blocks:
        if (table_region["x0"] <= block["bbox"]["x0"] <= table_region["x1"] and
            table_region["y0"] <= block["bbox"]["y0"] <= table_region["y1"]):
            table_texts.append(block)
    
    if not table_texts:
        return None
    
    # Cluster text by y-position to find rows
    y_positions = [block["bbox"]["y0"] for block in table_texts]
    y_clusters = _cluster_positions(y_positions, threshold=5)
    
    # Cluster text by x-position to find columns
    x_positions = [block["bbox"]["x0"] for block in table_texts]
    x_clusters = _cluster_positions(x_positions, threshold=20)
    
    # Build table structure
    rows = []
    for y_cluster in sorted(y_clusters):
        row_y = np.mean(y_cluster)
        row_texts = [t for t in table_texts 
                    if abs(t["bbox"]["y0"] - row_y) < 5]
        
        # Sort by x-position
        row_texts.sort(key=lambda t: t["bbox"]["x0"])
        
        # Assign to columns
        row_cells = [""] * len(x_clusters)
        for text in row_texts:
            x_pos = text["bbox"]["x0"]
            # Find which column this belongs to
            for col_idx, x_cluster in enumerate(x_clusters):
                if abs(x_pos - np.mean(x_cluster)) < 30:
                    if row_cells[col_idx]:
                        row_cells[col_idx] += " " + text["text"]
                    else:
                        row_cells[col_idx] = text["text"]
                    break
        
        rows.append(row_cells)
    
    return {
        "rows": rows,
        "num_rows": len(rows),
        "num_cols": len(x_clusters) if x_clusters else 0
    }


def _cluster_positions(positions: List[float], threshold: float) -> List[List[float]]:
    """Cluster positions that are close together."""
    if not positions:
        return []
    
    sorted_pos = sorted(set(positions))
    clusters = []
    current_cluster = [sorted_pos[0]]
    
    for pos in sorted_pos[1:]:
        if pos - current_cluster[-1] < threshold:
            current_cluster.append(pos)
        else:
            clusters.append(current_cluster)
            current_cluster = [pos]
    
    if current_cluster:
        clusters.append(current_cluster)
    
    return clusters


def validate_table(table_structure: Dict, table_region: Dict[str, float]) -> Tuple[bool, Dict[str, any]]:
    """
    Validate detected table using lightweight ML-based heuristics.
    Returns (is_valid, validation_info)
    """
    validation_info = {
        "has_consistent_columns": False,
        "has_multiple_rows": False,
        "has_header": False,
        "column_alignment_score": 0.0,
        "row_consistency_score": 0.0
    }
    
    if not table_structure or table_structure["num_rows"] < 2:
        return (False, validation_info)
    
    rows = table_structure["rows"]
    num_cols = table_structure["num_cols"]
    
    # Check for consistent column count
    col_counts = [len(row) for row in rows]
    if len(set(col_counts)) == 1 and col_counts[0] == num_cols:
        validation_info["has_consistent_columns"] = True
        validation_info["column_alignment_score"] = 1.0
    else:
        # Calculate alignment score based on consistency
        most_common_cols = max(set(col_counts), key=col_counts.count)
        consistency_ratio = col_counts.count(most_common_cols) / len(col_counts)
        validation_info["column_alignment_score"] = consistency_ratio
    
    # Check for multiple rows
    if len(rows) >= 2:
        validation_info["has_multiple_rows"] = True
        validation_info["row_consistency_score"] = min(1.0, len(rows) / 5.0)
    
    # Check for header row (first row might have different formatting)
    # This would require font information, simplified here
    if len(rows) >= 2:
        # Heuristic: if first row has non-empty cells, consider it a header
        first_row = rows[0]
        if any(cell.strip() for cell in first_row):
            validation_info["has_header"] = True
    
    # Overall validation: table is valid if it has consistent structure
    is_valid = (validation_info["has_consistent_columns"] and 
                validation_info["has_multiple_rows"] and
                validation_info["column_alignment_score"] > 0.5)
    
    return (is_valid, validation_info)


def extract_tables(page: fitz.Page) -> List[Dict]:
    """
    Main function to extract all tables from a page.
    Returns list of table dictionaries with structure and metadata.
    """
    tables = []
    
    # Detect table regions
    table_regions = detect_table_regions(page)
    
    for idx, region in enumerate(table_regions):
        # Reconstruct table structure
        table_structure = reconstruct_table_structure(page, region)
        
        if table_structure:
            # Validate table
            is_valid, validation_info = validate_table(table_structure, region)
            
            if is_valid or validation_info["column_alignment_score"] > 0.3:
                table_data = {
                    "table_id": f"table_{idx + 1}",
                    "bbox": region,
                    "structure": table_structure["rows"],
                    "num_rows": table_structure["num_rows"],
                    "num_cols": table_structure["num_cols"],
                    "validation": validation_info
                }
                tables.append(table_data)
    
    return tables

