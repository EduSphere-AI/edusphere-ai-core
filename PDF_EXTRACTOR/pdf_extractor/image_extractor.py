"""
Image extraction module.
Extracts raster images and associates them with titles/labels.
"""

import fitz  # PyMuPDF
import re
from typing import List, Dict, Optional
from .utils import get_bounding_box, boxes_intersect, extract_text_with_positions


def extract_images(page: fitz.Page) -> List[Dict]:
    """
    Extract all raster images from a page.
    Returns list of image dictionaries with metadata and associated text.
    """
    images = []
    
    # Get all images on the page
    image_list = page.get_images(full=True)
    
    for img_idx, img in enumerate(image_list):
        # Get image information
        xref = img[0]
        base_image = page.parent.extract_image(xref)
        
        # Get image bounding box
        # PyMuPDF stores images in the image list, but we need to find their positions
        # by checking the page's image references
        image_rects = page.get_image_rects(xref)
        
        if not image_rects:
            # If no rect found, try to get from page structure
            # This is a fallback - images might be embedded differently
            continue
        
        for rect in image_rects:
            image_bbox = get_bounding_box(rect)
            
            # Extract image metadata
            image_data = {
                "image_id": f"image_{img_idx + 1}",
                "xref": xref,
                "bbox": image_bbox,
                "width": base_image["width"],
                "height": base_image["height"],
                "colorspace": base_image["colorspace"],
                "bpc": base_image.get("bpc", 8),  # bits per component
                "ext": base_image["ext"],
                "size": base_image["image"].__sizeof__() if "image" in base_image else 0
            }
            
            # Check for text overlapping with image (embedded text in image)
            overlapping_text = _find_overlapping_text(page, image_bbox)
            if overlapping_text:
                image_data["embedded_text"] = [t["text"] for t in overlapping_text]
            else:
                image_data["embedded_text"] = []
            
            # Find associated title/label (e.g., "Figure X")
            label = _find_image_label(page, image_bbox)
            if label:
                image_data["label"] = label["text"]
                image_data["label_bbox"] = label["bbox"]
                image_data["figure_id"] = label.get("figure_id")
                image_data["figure_number"] = label.get("figure_number")
            else:
                image_data["label"] = None
                image_data["figure_id"] = None
                image_data["figure_number"] = None
            
            images.append(image_data)
    
    return images


def _find_overlapping_text(page: fitz.Page, image_bbox: Dict[str, float]) -> List[Dict]:
    """
    Find text that overlaps with the image bounding box.
    This might indicate text embedded in the image.
    """
    text_blocks = extract_text_with_positions(page)
    overlapping = []
    
    for block in text_blocks:
        # Check if text block overlaps significantly with image
        if boxes_intersect(block["bbox"], image_bbox, threshold=0.3):
            overlapping.append(block)
    
    return overlapping


def _find_image_label(page: fitz.Page, image_bbox: Dict[str, float]) -> Optional[Dict]:
    """
    Find label or title associated with the image (e.g., "Figure 1", "Fig. 2").
    Searches in text below, above, or near the image.
    """
    text_blocks = extract_text_with_positions(page)
    
    # Patterns for figure labels
    figure_patterns = [
        r'[Ff]igure\s+\d+',
        r'[Ff]ig\.\s*\d+',
        r'[Ff]ig\s+\d+',
        r'[Ii]mage\s+\d+',
        r'[Pp]hoto\s+\d+',
        r'[Pp]icture\s+\d+'
    ]
    
    # Search regions: below image (most common), above, and to the sides
    search_regions = [
        {
            "x0": image_bbox["x0"] - 50,
            "y0": image_bbox["y1"],
            "x1": image_bbox["x1"] + 50,
            "y1": image_bbox["y1"] + 80
        },
        {
            "x0": image_bbox["x0"] - 50,
            "y0": image_bbox["y0"] - 80,
            "x1": image_bbox["x1"] + 50,
            "y1": image_bbox["y0"]
        },
        {
            "x0": image_bbox["x1"],
            "y0": image_bbox["y0"] - 20,
            "x1": image_bbox["x1"] + 100,
            "y1": image_bbox["y1"] + 20
        },
        {
            "x0": image_bbox["x0"] - 100,
            "y0": image_bbox["y0"] - 20,
            "x1": image_bbox["x0"],
            "y1": image_bbox["y1"] + 20
        }
    ]
    
    for search_region in search_regions:
        for block in text_blocks:
            block_center_x = (block["bbox"]["x0"] + block["bbox"]["x1"]) / 2
            block_center_y = (block["bbox"]["y0"] + block["bbox"]["y1"]) / 2
            
            # Check if text is in search region
            if (search_region["x0"] <= block_center_x <= search_region["x1"] and
                search_region["y0"] <= block_center_y <= search_region["y1"]):
                
                text = block["text"]
                
                # Check for figure patterns
                for pattern in figure_patterns:
                    match = re.search(pattern, text)
                    if match:
                        # Extract figure number
                        num_match = re.search(r'\d+', text)
                        figure_num = num_match.group() if num_match else None
                        
                        return {
                            "text": text,
                            "bbox": block["bbox"],
                            "figure_id": f"figure_{figure_num}" if figure_num else None,
                            "figure_number": figure_num
                        }
                
                # Also check if text might be a caption (even without "Figure" keyword)
                # If it's directly below the image and short, it might be a label
                if (search_region == search_regions[0] and  # Below image
                    len(text.split()) < 20):  # Short text
                    return {
                        "text": text,
                        "bbox": block["bbox"],
                        "figure_id": None,
                        "figure_number": None
                    }
    
    return None

