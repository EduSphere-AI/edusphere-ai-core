#!/usr/bin/env python3
"""
CSV Export Module
Exports extracted PDF data to flat CSV format for ML models
"""

import json
import os
import csv
from typing import Dict, List, Any, Optional
import pandas as pd


class CSVExporter:
    """Export extracted PDF data to flat CSV format"""
    
    def __init__(self, extracted_data: Dict[str, Any], output_dir: str = "output"):
        """
        Initialize CSV exporter
        
        Args:
            extracted_data: JSON data from PDFExtractor
            output_dir: Directory for output CSV files
        """
        self.extracted_data = extracted_data
        self.output_dir = output_dir
        self.document = extracted_data.get("document", {})
        self.pages = self.document.get("pages", [])
        
        os.makedirs(output_dir, exist_ok=True)
    
    def export_content_blocks(self, output_path: Optional[str] = None) -> str:
        """
        Export content blocks to flat CSV
        
        Args:
            output_path: Path to save CSV file
            
        Returns:
            Path to saved CSV file
        """
        if output_path is None:
            output_path = os.path.join(self.output_dir, "content_blocks.csv")
        
        rows = []
        
        for page in self.pages:
            page_num = page.get("page_number", 0)
            
            for block in page.get("content_blocks", []):
                row = {
                    "id": block.get("id", ""),
                    "page_number": page_num,
                    "type": block.get("type", ""),
                    "text_type": block.get("text_type", ""),
                    "hierarchy_level": block.get("hierarchy_level", 5),
                    "content": block.get("content", ""),
                    "parent_id": block.get("parent_id", ""),
                    "children_ids": ",".join(block.get("children_ids", [])),
                    
                    # Position
                    "position_x0": block.get("position", {}).get("x0", 0),
                    "position_y0": block.get("position", {}).get("y0", 0),
                    "position_x1": block.get("position", {}).get("x1", 0),
                    "position_y1": block.get("position", {}).get("y1", 0),
                    
                    # Styling
                    "font_size": block.get("styling", {}).get("font_size", 0),
                    "font_weight": block.get("styling", {}).get("font_weight", ""),
                    "alignment": block.get("styling", {}).get("alignment", ""),
                    
                    # Language
                    "language_code": block.get("language", {}).get("code", ""),
                    "language_name": block.get("language", {}).get("name", ""),
                    "language_confidence": block.get("language", {}).get("confidence", 0.0),
                    "writing_system": block.get("language", {}).get("writing_system", ""),
                    
                    # Relationships
                    "table_id": block.get("relationships", {}).get("table_id", ""),
                    "figure_id": block.get("relationships", {}).get("figure_id", ""),
                    "footnote_ids": ",".join(block.get("relationships", {}).get("footnote_ids", [])),
                    
                    # Multi-column flag
                    "is_multi_column": block.get("is_multi_column", False),
                }
                
                # Add ML features if available
                ml_features = block.get("ml_features", {})
                if ml_features:
                    row.update({
                        "char_count": ml_features.get("char_count", 0),
                        "word_count": ml_features.get("word_count", 0),
                        "sentence_count": ml_features.get("sentence_count", 0),
                        "token_count": ml_features.get("token_count", 0),
                        "avg_word_length": ml_features.get("avg_word_length", 0),
                        "has_numbers": ml_features.get("has_numbers", False),
                        "has_special_chars": ml_features.get("has_special_chars", False),
                        "has_capitalized_words": ml_features.get("has_capitalized_words", False),
                        "ends_with_punctuation": ml_features.get("ends_with_punctuation", False),
                        "normalized_x0": ml_features.get("normalized_x0", 0),
                        "normalized_y0": ml_features.get("normalized_y0", 0),
                        "normalized_x1": ml_features.get("normalized_x1", 0),
                        "normalized_y1": ml_features.get("normalized_y1", 0),
                        "normalized_center_x": ml_features.get("normalized_center_x", 0),
                        "normalized_center_y": ml_features.get("normalized_center_y", 0),
                        "relative_to_page_center": ml_features.get("relative_to_page_center", 0),
                        "relative_page_position": ml_features.get("relative_page_position", 0),
                        "is_first_page": ml_features.get("is_first_page", False),
                        "is_last_page": ml_features.get("is_last_page", False),
                        "previous_block_type": ml_features.get("previous_block_type", ""),
                        "previous_block_hierarchy": ml_features.get("previous_block_hierarchy", ""),
                        "distance_to_previous": ml_features.get("distance_to_previous", ""),
                        "next_block_type": ml_features.get("next_block_type", ""),
                        "next_block_hierarchy": ml_features.get("next_block_hierarchy", ""),
                        "distance_to_next": ml_features.get("distance_to_next", ""),
                        "section_block_count": ml_features.get("section_block_count", 0),
                        "section_position": ml_features.get("section_position", 0),
                        "font_weight_bold": ml_features.get("font_weight_bold", 0),
                        "alignment_left": ml_features.get("alignment_left", 0),
                        "alignment_center": ml_features.get("alignment_center", 0),
                        "alignment_right": ml_features.get("alignment_right", 0),
                        "is_title": ml_features.get("is_title", 0),
                        "is_heading": ml_features.get("is_heading", 0),
                        "is_paragraph": ml_features.get("is_paragraph", 0),
                        "has_table": ml_features.get("has_table", 0),
                        "has_figure": ml_features.get("has_figure", 0),
                        "has_footnotes": ml_features.get("has_footnotes", 0),
                        "footnote_count": ml_features.get("footnote_count", 0),
                        "writing_system_ltr": ml_features.get("writing_system_ltr", 0),
                        "writing_system_rtl": ml_features.get("writing_system_rtl", 0),
                    })
                
                rows.append(row)
        
        # Write to CSV
        if rows:
            df = pd.DataFrame(rows)
            df.to_csv(output_path, index=False, encoding='utf-8')
            print(f"Exported {len(rows)} content blocks to {output_path}")
        
        return output_path
    
    def export_tables(self, output_path: Optional[str] = None) -> str:
        """
        Export table data to CSV
        
        Args:
            output_path: Path to save CSV file
            
        Returns:
            Path to saved CSV file
        """
        if output_path is None:
            output_path = os.path.join(self.output_dir, "tables.csv")
        
        rows = []
        
        for page in self.pages:
            page_num = page.get("page_number", 0)
            
            for table in page.get("tables", []):
                table_id = table.get("id", "")
                caption = table.get("caption", "")
                
                for cell in table.get("data", []):
                    row = {
                        "table_id": table_id,
                        "page_number": page_num,
                        "caption": caption,
                        "row": cell.get("row", 0),
                        "column": cell.get("column", 0),
                        "content": cell.get("content", ""),
                        "is_header": cell.get("is_header", False),
                        "language_code": cell.get("language", {}).get("code", ""),
                        "language_name": cell.get("language", {}).get("name", ""),
                        "position_x0": table.get("position", {}).get("x0", 0),
                        "position_y0": table.get("position", {}).get("y0", 0),
                        "position_x1": table.get("position", {}).get("x1", 0),
                        "position_y1": table.get("position", {}).get("y1", 0),
                        "table_rows": table.get("structure", {}).get("rows", 0),
                        "table_columns": table.get("structure", {}).get("columns", 0),
                        "has_header": table.get("structure", {}).get("has_header", False),
                    }
                    rows.append(row)
        
        # Write to CSV
        if rows:
            df = pd.DataFrame(rows)
            df.to_csv(output_path, index=False, encoding='utf-8')
            print(f"Exported {len(rows)} table cells to {output_path}")
        else:
            # Create empty CSV with headers
            df = pd.DataFrame(columns=[
                "table_id", "page_number", "caption", "row", "column", "content",
                "is_header", "language_code", "language_name",
                "position_x0", "position_y0", "position_x1", "position_y1",
                "table_rows", "table_columns", "has_header"
            ])
            df.to_csv(output_path, index=False, encoding='utf-8')
            print(f"Created empty tables CSV at {output_path}")
        
        return output_path
    
    def export_chart_data(self, output_path: Optional[str] = None) -> str:
        """
        Export chart data to CSV (one row per data point)
        
        Args:
            output_path: Path to save CSV file
            
        Returns:
            Path to saved CSV file
        """
        if output_path is None:
            output_path = os.path.join(self.output_dir, "chart_data.csv")
        
        rows = []
        
        for page in self.pages:
            page_num = page.get("page_number", 0)
            
            for figure in page.get("figures", []):
                figure_id = figure.get("id", "")
                chart_data = figure.get("chart_data")
                
                if chart_data:
                    chart_type = chart_data.get("chart_type", "unknown")
                    
                    for series in chart_data.get("series", []):
                        series_name = series.get("name", "")
                        
                        for data_point in series.get("data_points", []):
                            row = {
                                "figure_id": figure_id,
                                "page_number": page_num,
                                "chart_type": chart_type,
                                "series_name": series_name,
                                "category": data_point.get("category", ""),
                                "value": data_point.get("value", ""),
                                "unit": data_point.get("unit", ""),
                                "text_context": data_point.get("text_context", ""),
                                "caption": figure.get("caption", ""),
                                "position_x0": figure.get("position", {}).get("x0", 0),
                                "position_y0": figure.get("position", {}).get("y0", 0),
                                "position_x1": figure.get("position", {}).get("x1", 0),
                                "position_y1": figure.get("position", {}).get("y1", 0),
                            }
                            rows.append(row)
        
        # Write to CSV
        if rows:
            df = pd.DataFrame(rows)
            df.to_csv(output_path, index=False, encoding='utf-8')
            print(f"Exported {len(rows)} chart data points to {output_path}")
        else:
            # Create empty CSV with headers
            df = pd.DataFrame(columns=[
                "figure_id", "page_number", "chart_type", "series_name", "category",
                "value", "unit", "text_context", "caption",
                "position_x0", "position_y0", "position_x1", "position_y1"
            ])
            df.to_csv(output_path, index=False, encoding='utf-8')
            print(f"Created empty chart_data CSV at {output_path}")
        
        return output_path
    
    def export_all_to_single_file(self, output_path: Optional[str] = None) -> str:
        """
        Export all data types to a single consolidated CSV file
        
        Args:
            output_path: Path to save consolidated CSV file
            
        Returns:
            Path to saved CSV file
        """
        if output_path is None:
            output_path = os.path.join(self.output_dir, "extracted_data.csv")
        
        rows = []
        
        # Add content blocks
        for page in self.pages:
            page_num = page.get("page_number", 0)
            
            for block in page.get("content_blocks", []):
                row = {
                    "data_type": "content_block",
                    "id": block.get("id", ""),
                    "page_number": page_num,
                    "type": block.get("type", ""),
                    "text_type": block.get("text_type", ""),
                    "hierarchy_level": block.get("hierarchy_level", 5),
                    "content": block.get("content", ""),
                    "parent_id": block.get("parent_id", ""),
                    "children_ids": ",".join(block.get("children_ids", [])),
                    
                    # Position
                    "position_x0": block.get("position", {}).get("x0", 0),
                    "position_y0": block.get("position", {}).get("y0", 0),
                    "position_x1": block.get("position", {}).get("x1", 0),
                    "position_y1": block.get("position", {}).get("y1", 0),
                    
                    # Styling
                    "font_size": block.get("styling", {}).get("font_size", 0),
                    "font_weight": block.get("styling", {}).get("font_weight", ""),
                    "alignment": block.get("styling", {}).get("alignment", ""),
                    
                    # Language
                    "language_code": block.get("language", {}).get("code", ""),
                    "language_name": block.get("language", {}).get("name", ""),
                    "language_confidence": block.get("language", {}).get("confidence", 0.0),
                    "writing_system": block.get("language", {}).get("writing_system", ""),
                    
                    # Relationships
                    "table_id": block.get("relationships", {}).get("table_id", ""),
                    "figure_id": block.get("relationships", {}).get("figure_id", ""),
                    "footnote_ids": ",".join(block.get("relationships", {}).get("footnote_ids", [])),
                    
                    # Multi-column flag
                    "is_multi_column": block.get("is_multi_column", False),
                    
                    # Table/Chart specific fields (empty for content blocks)
                    "table_row": "",
                    "table_column": "",
                    "is_header": "",
                    "table_rows": "",
                    "table_columns": "",
                    "chart_type": "",
                    "series_name": "",
                    "category": "",
                    "value": "",
                    "unit": "",
                }
                
                # Add ML features if available
                ml_features = block.get("ml_features", {})
                if ml_features:
                    row.update({
                        "char_count": ml_features.get("char_count", 0),
                        "word_count": ml_features.get("word_count", 0),
                        "sentence_count": ml_features.get("sentence_count", 0),
                        "token_count": ml_features.get("token_count", 0),
                        "avg_word_length": ml_features.get("avg_word_length", 0),
                        "has_numbers": ml_features.get("has_numbers", False),
                        "has_special_chars": ml_features.get("has_special_chars", False),
                        "has_capitalized_words": ml_features.get("has_capitalized_words", False),
                        "ends_with_punctuation": ml_features.get("ends_with_punctuation", False),
                        "normalized_x0": ml_features.get("normalized_x0", 0),
                        "normalized_y0": ml_features.get("normalized_y0", 0),
                        "normalized_x1": ml_features.get("normalized_x1", 0),
                        "normalized_y1": ml_features.get("normalized_y1", 0),
                        "normalized_center_x": ml_features.get("normalized_center_x", 0),
                        "normalized_center_y": ml_features.get("normalized_center_y", 0),
                        "relative_to_page_center": ml_features.get("relative_to_page_center", 0),
                        "relative_page_position": ml_features.get("relative_page_position", 0),
                        "is_first_page": ml_features.get("is_first_page", False),
                        "is_last_page": ml_features.get("is_last_page", False),
                        "previous_block_type": ml_features.get("previous_block_type", ""),
                        "previous_block_hierarchy": ml_features.get("previous_block_hierarchy", ""),
                        "distance_to_previous": ml_features.get("distance_to_previous", ""),
                        "next_block_type": ml_features.get("next_block_type", ""),
                        "next_block_hierarchy": ml_features.get("next_block_hierarchy", ""),
                        "distance_to_next": ml_features.get("distance_to_next", ""),
                        "section_block_count": ml_features.get("section_block_count", 0),
                        "section_position": ml_features.get("section_position", 0),
                        "font_weight_bold": ml_features.get("font_weight_bold", 0),
                        "alignment_left": ml_features.get("alignment_left", 0),
                        "alignment_center": ml_features.get("alignment_center", 0),
                        "alignment_right": ml_features.get("alignment_right", 0),
                        "is_title": ml_features.get("is_title", 0),
                        "is_heading": ml_features.get("is_heading", 0),
                        "is_paragraph": ml_features.get("is_paragraph", 0),
                        "has_table": ml_features.get("has_table", 0),
                        "has_figure": ml_features.get("has_figure", 0),
                        "has_footnotes": ml_features.get("has_footnotes", 0),
                        "footnote_count": ml_features.get("footnote_count", 0),
                        "writing_system_ltr": ml_features.get("writing_system_ltr", 0),
                        "writing_system_rtl": ml_features.get("writing_system_rtl", 0),
                    })
                else:
                    # Add empty ML feature columns if not available
                    ml_cols = ["char_count", "word_count", "sentence_count", "token_count", "avg_word_length",
                              "has_numbers", "has_special_chars", "has_capitalized_words", "ends_with_punctuation",
                              "normalized_x0", "normalized_y0", "normalized_x1", "normalized_y1",
                              "normalized_center_x", "normalized_center_y", "relative_to_page_center",
                              "relative_page_position", "is_first_page", "is_last_page",
                              "previous_block_type", "previous_block_hierarchy", "distance_to_previous",
                              "next_block_type", "next_block_hierarchy", "distance_to_next",
                              "section_block_count", "section_position",
                              "font_weight_bold", "alignment_left", "alignment_center", "alignment_right",
                              "is_title", "is_heading", "is_paragraph", "has_table", "has_figure",
                              "has_footnotes", "footnote_count", "writing_system_ltr", "writing_system_rtl"]
                    for col in ml_cols:
                        row[col] = ""
                
                rows.append(row)
        
        # Add table cells
        for page in self.pages:
            page_num = page.get("page_number", 0)
            
            for table in page.get("tables", []):
                table_id = table.get("id", "")
                caption = table.get("caption", "")
                
                for cell in table.get("data", []):
                    row = {
                        "data_type": "table_cell",
                        "id": f"{table_id}_cell_{cell.get('row', 0)}_{cell.get('column', 0)}",
                        "page_number": page_num,
                        "type": "table",
                        "text_type": "",
                        "hierarchy_level": "",
                        "content": cell.get("content", ""),
                        "parent_id": table_id,
                        "children_ids": "",
                        
                        # Position (table position)
                        "position_x0": table.get("position", {}).get("x0", 0),
                        "position_y0": table.get("position", {}).get("y0", 0),
                        "position_x1": table.get("position", {}).get("x1", 0),
                        "position_y1": table.get("position", {}).get("y1", 0),
                        
                        # Styling (empty for table cells)
                        "font_size": "",
                        "font_weight": "",
                        "alignment": "",
                        
                        # Language
                        "language_code": cell.get("language", {}).get("code", ""),
                        "language_name": cell.get("language", {}).get("name", ""),
                        "language_confidence": cell.get("language", {}).get("confidence", 0.0),
                        "writing_system": cell.get("language", {}).get("writing_system", ""),
                        
                        # Relationships
                        "table_id": table_id,
                        "figure_id": "",
                        "footnote_ids": "",
                        
                        # Multi-column flag
                        "is_multi_column": False,
                        
                        # Table specific fields
                        "table_row": cell.get("row", 0),
                        "table_column": cell.get("column", 0),
                        "is_header": cell.get("is_header", False),
                        "table_rows": table.get("structure", {}).get("rows", 0),
                        "table_columns": table.get("structure", {}).get("columns", 0),
                        "chart_type": "",
                        "series_name": "",
                        "category": "",
                        "value": "",
                        "unit": "",
                    }
                    
                    # Add empty ML feature columns for table cells
                    ml_cols = ["char_count", "word_count", "sentence_count", "token_count", "avg_word_length",
                              "has_numbers", "has_special_chars", "has_capitalized_words", "ends_with_punctuation",
                              "normalized_x0", "normalized_y0", "normalized_x1", "normalized_y1",
                              "normalized_center_x", "normalized_center_y", "relative_to_page_center",
                              "relative_page_position", "is_first_page", "is_last_page",
                              "previous_block_type", "previous_block_hierarchy", "distance_to_previous",
                              "next_block_type", "next_block_hierarchy", "distance_to_next",
                              "section_block_count", "section_position",
                              "font_weight_bold", "alignment_left", "alignment_center", "alignment_right",
                              "is_title", "is_heading", "is_paragraph", "has_table", "has_figure",
                              "has_footnotes", "footnote_count", "writing_system_ltr", "writing_system_rtl"]
                    for col in ml_cols:
                        row[col] = ""
                    
                    rows.append(row)
        
        # Add chart data points
        for page in self.pages:
            page_num = page.get("page_number", 0)
            
            for figure in page.get("figures", []):
                figure_id = figure.get("id", "")
                chart_data = figure.get("chart_data")
                
                if chart_data:
                    chart_type = chart_data.get("chart_type", "unknown")
                    
                    for series in chart_data.get("series", []):
                        series_name = series.get("name", "")
                        
                        for idx, data_point in enumerate(series.get("data_points", [])):
                            row = {
                                "data_type": "chart_data",
                                "id": f"{figure_id}_point_{idx}",
                                "page_number": page_num,
                                "type": "chart",
                                "text_type": "",
                                "hierarchy_level": "",
                                "content": data_point.get("text_context", ""),
                                "parent_id": figure_id,
                                "children_ids": "",
                                
                                # Position (figure position)
                                "position_x0": figure.get("position", {}).get("x0", 0),
                                "position_y0": figure.get("position", {}).get("y0", 0),
                                "position_x1": figure.get("position", {}).get("x1", 0),
                                "position_y1": figure.get("position", {}).get("y1", 0),
                                
                                # Styling (empty for chart data)
                                "font_size": "",
                                "font_weight": "",
                                "alignment": "",
                                
                                # Language (empty for chart data)
                                "language_code": "",
                                "language_name": "",
                                "language_confidence": "",
                                "writing_system": "",
                                
                                # Relationships
                                "table_id": "",
                                "figure_id": figure_id,
                                "footnote_ids": "",
                                
                                # Multi-column flag
                                "is_multi_column": False,
                                
                                # Table specific fields (empty)
                                "table_row": "",
                                "table_column": "",
                                "is_header": "",
                                "table_rows": "",
                                "table_columns": "",
                                
                                # Chart specific fields
                                "chart_type": chart_type,
                                "series_name": series_name,
                                "category": data_point.get("category", ""),
                                "value": data_point.get("value", ""),
                                "unit": data_point.get("unit", ""),
                            }
                            
                            # Add empty ML feature columns for chart data
                            ml_cols = ["char_count", "word_count", "sentence_count", "token_count", "avg_word_length",
                                      "has_numbers", "has_special_chars", "has_capitalized_words", "ends_with_punctuation",
                                      "normalized_x0", "normalized_y0", "normalized_x1", "normalized_y1",
                                      "normalized_center_x", "normalized_center_y", "relative_to_page_center",
                                      "relative_page_position", "is_first_page", "is_last_page",
                                      "previous_block_type", "previous_block_hierarchy", "distance_to_previous",
                                      "next_block_type", "next_block_hierarchy", "distance_to_next",
                                      "section_block_count", "section_position",
                                      "font_weight_bold", "alignment_left", "alignment_center", "alignment_right",
                                      "is_title", "is_heading", "is_paragraph", "has_table", "has_figure",
                                      "has_footnotes", "footnote_count", "writing_system_ltr", "writing_system_rtl"]
                            for col in ml_cols:
                                row[col] = ""
                            
                            rows.append(row)
        
        # Write to CSV
        if rows:
            df = pd.DataFrame(rows)
            df.to_csv(output_path, index=False, encoding='utf-8')
            print(f"Exported {len(rows)} rows to consolidated CSV: {output_path}")
            print(f"  - Content blocks: {sum(1 for r in rows if r['data_type'] == 'content_block')}")
            print(f"  - Table cells: {sum(1 for r in rows if r['data_type'] == 'table_cell')}")
            print(f"  - Chart data points: {sum(1 for r in rows if r['data_type'] == 'chart_data')}")
        
        return output_path
    
    def export_all(self, prefix: str = "", single_file: bool = False) -> Dict[str, str]:
        """
        Export all data types to CSV files
        
        Args:
            prefix: Optional prefix for output filenames
            single_file: If True, export everything to a single file
            
        Returns:
            Dictionary mapping data type to output file path
        """
        if single_file:
            output_path = os.path.join(self.output_dir, f"{prefix}extracted_data.csv" if prefix else "extracted_data.csv")
            path = self.export_all_to_single_file(output_path)
            return {"all_data": path}
        
        outputs = {}
        
        content_path = os.path.join(self.output_dir, f"{prefix}content_blocks.csv" if prefix else "content_blocks.csv")
        tables_path = os.path.join(self.output_dir, f"{prefix}tables.csv" if prefix else "tables.csv")
        charts_path = os.path.join(self.output_dir, f"{prefix}chart_data.csv" if prefix else "chart_data.csv")
        
        outputs["content_blocks"] = self.export_content_blocks(content_path)
        outputs["tables"] = self.export_tables(tables_path)
        outputs["chart_data"] = self.export_chart_data(charts_path)
        
        print(f"\nCSV export complete! Files saved to {self.output_dir}")
        return outputs


def main():
    """Main function for command-line usage"""
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description="Export extracted PDF data to CSV format")
    parser.add_argument("input_json", help="Path to extracted_data.json file")
    parser.add_argument("output_dir", nargs="?", default="output", help="Output directory (default: output)")
    parser.add_argument("--single-file", action="store_true", default=True,
                       help="Export all data to a single CSV file (default: True)")
    parser.add_argument("--separate-files", action="store_true",
                       help="Export to separate CSV files (content_blocks, tables, chart_data)")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.input_json):
        print(f"Error: Input file not found: {args.input_json}")
        sys.exit(1)
    
    # Load extracted data
    print(f"Loading extracted data from: {args.input_json}")
    with open(args.input_json, "r", encoding="utf-8") as f:
        extracted_data = json.load(f)
    
    # Export to CSV
    exporter = CSVExporter(extracted_data, args.output_dir)
    
    if args.separate_files:
        exporter.export_all(single_file=False)
    else:
        exporter.export_all(single_file=True)


if __name__ == "__main__":
    main()

