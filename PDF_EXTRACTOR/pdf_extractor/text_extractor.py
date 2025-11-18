"""
Text extraction module with categorization.
Extracts and categorizes text excluding content from tables, charts, and images.
"""

import fitz  # PyMuPDF
import numpy as np
from typing import List, Dict, Set, Optional
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from .utils import extract_text_with_positions, text_in_box


class TextCategorizer:
    """
    ML-based text categorizer using heuristics and simple classification.
    """
    
    def __init__(self):
        self.classifier = None
        self.scaler = StandardScaler()
        self.is_trained = False
    
    def extract_features(self, text_block: Dict, page_width: float, page_height: float) -> List[float]:
        """
        Extract features from a text block for classification.
        """
        font = text_block["font"]
        bbox = text_block["bbox"]
        
        features = [
            font["size"],  # Font size
            1.0 if font["is_bold"] else 0.0,  # Is bold
            1.0 if font["is_italic"] else 0.0,  # Is italic
            bbox["y0"] / page_height,  # Relative vertical position (0 = top, 1 = bottom)
            bbox["x0"] / page_width,  # Relative horizontal position
            (bbox["x1"] - bbox["x0"]) / page_width,  # Relative width
            len(text_block["text"]),  # Text length
            text_block["text"].count(" "),  # Word count (approximate)
            1.0 if text_block["text"].strip().startswith('"') else 0.0,  # Starts with quote
            1.0 if text_block["text"].strip().endswith('"') else 0.0,  # Ends with quote
            text_block["text"].count('"'),  # Number of quotes
            text_block["text"].count("'"),  # Number of single quotes
        ]
        
        return features
    
    def train(self, text_blocks: List[Dict], labels: List[str], page_width: float, page_height: float):
        """
        Train the classifier on labeled examples.
        For now, we'll use rule-based labeling for training.
        """
        if not text_blocks:
            return
        
        # Extract features
        X = np.array([self.extract_features(block, page_width, page_height) 
                     for block in text_blocks])
        y = np.array(labels)
        
        # Scale features
        X_scaled = self.scaler.fit_transform(X)
        
        # Train classifier
        self.classifier = RandomForestClassifier(n_estimators=50, random_state=42)
        self.classifier.fit(X_scaled, y)
        self.is_trained = True
    
    def predict(self, text_block: Dict, page_width: float, page_height: float) -> str:
        """
        Predict category for a text block.
        Falls back to rule-based if classifier not trained.
        """
        if self.is_trained and self.classifier:
            features = np.array([self.extract_features(text_block, page_width, page_height)])
            features_scaled = self.scaler.transform(features)
            return self.classifier.predict(features_scaled)[0]
        else:
            # Fall back to rule-based classification
            return self._rule_based_classify(text_block, page_width, page_height)
    
    def _rule_based_classify(self, text_block: Dict, page_width: float, page_height: float) -> str:
        """
        Rule-based text categorization using heuristics.
        """
        font = text_block["font"]
        bbox = text_block["bbox"]
        text = text_block["text"].strip()
        
        # Relative position on page
        rel_y = bbox["y0"] / page_height
        rel_x = bbox["x0"] / page_width
        
        # Check for citations/quotes
        if (text.startswith('"') and text.endswith('"')) or \
           (text.startswith("'") and text.endswith("'")) or \
           font["is_italic"] or \
           (rel_x > 0.1 and rel_x < 0.9 and len(text) > 20 and text.count('"') >= 2):
            return "citation"
        
        # Check for titles
        if (font["size"] > 14 or font["is_bold"]) and \
           (rel_y < 0.15 or abs(rel_x - 0.5) < 0.2) and \
           len(text) < 200:
            return "title"
        
        # Check for subtitles
        if (font["size"] > 11 or font["is_bold"]) and \
           (rel_y < 0.3) and \
           len(text) < 150:
            return "subtitle"
        
        # Default to body text
        return "body"


def filter_text_by_exclusions(text_blocks: List[Dict], 
                              table_regions: List[Dict[str, float]],
                              chart_regions: List[Dict[str, float]],
                              image_regions: List[Dict[str, float]]) -> List[Dict]:
    """
    Filter out text that overlaps with tables, charts, or images.
    """
    excluded_indices: Set[int] = set()
    
    # Check each text block against exclusion regions
    for idx, text_block in enumerate(text_blocks):
        text_bbox = text_block["bbox"]
        
        # Check against tables
        for table_region in table_regions:
            if text_in_box(text_bbox, table_region, threshold=0.5):
                excluded_indices.add(idx)
                break
        
        if idx in excluded_indices:
            continue
        
        # Check against charts
        for chart_region in chart_regions:
            if text_in_box(text_bbox, chart_region, threshold=0.5):
                excluded_indices.add(idx)
                break
        
        if idx in excluded_indices:
            continue
        
        # Check against images
        for image_region in image_regions:
            if text_in_box(text_bbox, image_region, threshold=0.5):
                excluded_indices.add(idx)
                break
    
    # Return filtered text blocks
    return [block for idx, block in enumerate(text_blocks) if idx not in excluded_indices]


def extract_text(page: fitz.Page,
                table_regions: List[Dict[str, float]],
                chart_regions: List[Dict[str, float]],
                image_regions: List[Dict[str, float]],
                categorizer: Optional[TextCategorizer] = None) -> Dict[str, List[Dict]]:
    """
    Extract and categorize text from a page, excluding text in tables, charts, and images.
    
    Returns dictionary with categorized text:
    {
        "titles": [...],
        "subtitles": [...],
        "body": [...],
        "citations": [...]
    }
    """
    # Extract all text with positions
    all_text_blocks = extract_text_with_positions(page)
    
    # Filter out text in excluded regions
    filtered_text = filter_text_by_exclusions(
        all_text_blocks,
        table_regions,
        chart_regions,
        image_regions
    )
    
    if not filtered_text:
        return {
            "titles": [],
            "subtitles": [],
            "body": [],
            "citations": []
        }
    
    # Get page dimensions
    page_rect = page.rect
    page_width = page_rect.width
    page_height = page_rect.height
    
    # Initialize categorizer if not provided
    if categorizer is None:
        categorizer = TextCategorizer()
    
    # Categorize text
    categorized = {
        "titles": [],
        "subtitles": [],
        "body": [],
        "citations": []
    }
    
    for text_block in filtered_text:
        category = categorizer.predict(text_block, page_width, page_height)
        
        # Add text block with category
        text_data = {
            "text": text_block["text"],
            "bbox": text_block["bbox"],
            "font": text_block["font"],
            "category": category
        }
        
        if category == "title":
            categorized["titles"].append(text_data)
        elif category == "subtitle":
            categorized["subtitles"].append(text_data)
        elif category == "citation":
            categorized["citations"].append(text_data)
        else:  # body
            categorized["body"].append(text_data)
    
    return categorized

