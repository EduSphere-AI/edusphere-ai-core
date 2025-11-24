# PDF Data Extraction Methods - Recommendations

## Overview
This document outlines recommended methods for extracting different data types from PDFs for micro-course content transformation. The extraction should preserve structure, relationships, and context without using OCR.

---

## 1. TEXT EXTRACTION

### Recommended Libraries & Methods:

#### **Primary Method: PyMuPDF (fitz)**
- **Why:** Excellent for extracting text with positioning, font information, and maintaining structure
- **Capabilities:**
  - Text extraction with bounding boxes (coordinates)
  - Font size, style, and family detection
  - Page-by-page structured extraction
  - Handles text in various encodings
  - Can identify text blocks, lines, and spans

#### **Alternative Method: pdfplumber**
- **Why:** Great for structured text extraction with layout awareness
- **Capabilities:**
  - Extracts text with positioning and styling
  - Identifies text blocks and their hierarchy
  - Can detect text in different regions (headers, footers, margins)
  - Maintains reading order

#### **Methodology:**
1. **Hierarchy Detection:**
   - Analyze font sizes to identify titles (largest), subtitles, headers, body text
   - Use font weight (bold) for emphasis detection
   - Consider vertical spacing between blocks
   - Use indentation for lists and nested structures

2. **Text Type Classification:**
   - **Title:** Largest font size, centered/top position, often bold
   - **Subtitle/Heading:** Medium-large font, bold, specific spacing
   - **Paragraph:** Regular font size, justified/left-aligned, regular weight
   - **Author/Metadata:** Often in specific regions (header/footer), smaller font
   - **Caption:** Smaller font, near figures/tables, often italicized
   - **Footnote:** Very small font, at bottom of page, numbered

3. **Relationships Preservation:**
   - Track parent-child relationships (section → subsection)
   - Maintain reading order (top-to-bottom, left-to-right)
   - Link captions to their figures/tables
   - Connect footnotes to their references

---

## 2. TABLE EXTRACTION

### Recommended Libraries & Methods:

#### **Primary Method: pdfplumber**
- **Why:** Most accurate for complex table structures with merged cells
- **Capabilities:**
  - Detects table boundaries automatically
  - Handles merged cells
  - Preserves cell relationships and structure
  - Extracts text with cell coordinates
  - Can detect header rows

#### **Alternative Method: Camelot-py**
- **Why:** Excellent for well-structured tables with clear boundaries
- **Capabilities:**
  - Lattice method for tables with clear lines
  - Stream method for tables without visible borders
  - Returns DataFrame structure
  - Provides table coordinates

#### **Alternative Method: PyMuPDF (fitz)**
- **Why:** Good for basic table extraction with precise coordinate tracking
- **Capabilities:**
  - Manual table detection using text positioning
  - Custom table parsing logic
  - Full control over extraction process

#### **Methodology:**
1. **Table Detection:**
   - Identify regions with aligned text (columns)
   - Detect horizontal and vertical lines
   - Use text density analysis

2. **Structure Preservation:**
   - Store as 2D array with row/column indices
   - Preserve merged cell information
   - Identify and tag header rows/columns
   - Store cell coordinates (bounding boxes)

3. **Text Extraction:**
   - Extract text from each cell separately
   - Maintain cell formatting (if any)
   - Handle empty cells
   - Preserve numerical formatting

---

## 3. IMAGE/CHART EXTRACTION

### Recommended Libraries & Methods:

#### **Primary Method: PyMuPDF (fitz)**
- **Why:** Best for extracting images and their metadata together
- **Capabilities:**
  - Extract images at original quality
  - Get image coordinates (bounding boxes)
  - Extract embedded images (charts, diagrams)
  - Identify image formats (JPEG, PNG, etc.)

#### **Alternative Method: pdf2image + Pillow**
- **Why:** Good for rendering entire pages as images
- **Capabilities:**
  - Convert PDF pages to images
  - Extract regions of interest
  - Good for complex layouts

#### **Methodology:**
1. **Image Detection:**
   - Extract all image objects from PDF
   - Get bounding box coordinates
   - Identify image types (photograph, chart, diagram, logo)

2. **Text Overlay Extraction:**
   - Extract text that overlaps or is near images (labels, annotations)
   - Store text with relative positioning to image
   - Identify text that is part of the image vs. separate overlay

3. **Caption Association:**
   - Find text immediately below/above images (captions)
   - Look for patterns like "Figure 1:", "Chart:", etc.
   - Store caption text separately but linked to image

4. **Classification:**
   - **Chart/Graph:** Contains data visualizations
   - **Diagram:** Contains structural illustrations
   - **Photograph:** Real-world images
   - **Logo/Icon:** Small decorative elements

---

## 4. DIAGRAM/FIGURE EXTRACTION

### Recommended Methods:

#### **Primary Method: PyMuPDF (fitz) + Custom Logic**
- **Why:** Diagrams often combine vector graphics and text overlays
- **Capabilities:**
   - Extract vector paths (if applicable)
   - Extract embedded images
   - Separate text annotations from graphics
   - Preserve coordinate systems

#### **Methodology:**
1. **Figure Region Detection:**
   - Identify regions with dense graphics (low text density but visual elements)
   - Use bounding boxes for figure areas

2. **Text Component Extraction:**
   - Extract all text within figure boundaries
   - Store text with coordinates relative to figure
   - Identify text roles (labels, annotations, axis labels, legends)

3. **Structure Preservation:**
   - Store figure as image asset
   - Store text components separately with positioning
   - Create mapping between text and its visual location

---

## 5. METADATA EXTRACTION

### Recommended Methods:

#### **Primary Method: PyPDF2 or PyMuPDF**
- **Capabilities:**
  - Extract PDF metadata (title, author, creation date, etc.)
  - Extract document-level properties
  - Get page count, dimensions

#### **Methodology:**
1. **Document Metadata:**
   - Title, author, subject, keywords
   - Creation and modification dates
   - PDF version, producer information

2. **Structural Metadata:**
   - Number of pages
   - Page dimensions
   - Document outline/bookmarks (if present)

---

## RECOMMENDED DATA STRUCTURE (JSON Schema)

```json
{
  "document": {
    "metadata": {
      "title": "string",
      "author": "string",
      "creation_date": "datetime",
      "page_count": "integer",
      "source_file": "string"
    },
    "pages": [
      {
        "page_number": "integer",
        "dimensions": {
          "width": "float",
          "height": "float"
        },
        "content_blocks": [
          {
            "id": "string",
            "type": "text|table|image|figure|metadata",
            "hierarchy_level": "integer",
            "text_type": "title|subtitle|heading|paragraph|caption|footnote|author|metadata",
            "content": "string|object",
            "position": {
              "x0": "float",
              "y0": "float",
              "x1": "float",
              "y1": "float"
            },
            "styling": {
              "font_size": "float",
              "font_family": "string",
              "font_weight": "string",
              "alignment": "string"
            },
            "parent_id": "string|null",
            "children_ids": ["string"],
            "relationships": {
              "figure_id": "string|null",
              "table_id": "string|null",
              "footnote_ids": ["string"]
            }
          }
        ],
        "tables": [
          {
            "id": "string",
            "caption": "string|null",
            "position": {
              "x0": "float",
              "y0": "float",
              "x1": "float",
              "y1": "float"
            },
            "structure": {
              "rows": "integer",
              "columns": "integer",
              "has_header": "boolean"
            },
            "data": [
              {
                "row": "integer",
                "column": "integer",
                "content": "string",
                "is_header": "boolean",
                "merged_cells": "object|null"
              }
            ]
          }
        ],
        "images": [
          {
            "id": "string",
            "type": "chart|diagram|photograph|logo",
            "caption": "string|null",
            "position": {
              "x0": "float",
              "y0": "float",
              "x1": "float",
              "y1": "float"
            },
            "file_path": "string",
            "embedded_text": [
              {
                "text": "string",
                "position": {
                  "x0": "float",
                  "y0": "float",
                  "x1": "float",
                  "y1": "float"
                },
                "relative_position": {
                  "x": "float",
                  "y": "float"
                }
              }
            ]
          }
        ]
      }
    ]
  }
}
```

---

## IMPLEMENTATION PRIORITY

1. **Phase 1: Text Extraction**
   - Implement PyMuPDF-based text extraction
   - Develop hierarchy detection algorithm
   - Classify text types

2. **Phase 2: Table Extraction**
   - Implement pdfplumber table extraction
   - Structure table data
   - Link tables to captions

3. **Phase 3: Image/Figure Extraction**
   - Extract images and figures
   - Separate text overlays
   - Associate captions

4. **Phase 4: Relationship Mapping**
   - Build parent-child relationships
   - Link figures to captions
   - Connect footnotes to references

5. **Phase 5: Noise Reduction**
   - Remove header/footer repetitions
   - Clean extracted text
   - Validate structure consistency

---

## NOISE REDUCTION STRATEGIES

1. **Header/Footer Removal:**
   - Identify repeated text at top/bottom of pages
   - Remove if appearing on multiple consecutive pages

2. **Text Cleaning:**
   - Remove excessive whitespace
   - Fix broken words across lines
   - Normalize encoding issues

3. **Duplicate Detection:**
   - Identify and remove duplicate content blocks
   - Handle page numbers and repeated elements

4. **Validation:**
   - Verify hierarchy consistency
   - Check for orphaned references
   - Validate relationships

---

## RECOMMENDED PYTHON PACKAGES

```python
# Core extraction
PyMuPDF (fitz)        # Primary: text, images, structure
pdfplumber            # Alternative: text, tables
PyPDF2                # Metadata extraction

# Image processing
Pillow (PIL)          # Image manipulation
pdf2image             # PDF to image conversion

# Data handling
pandas                # Table data structures
numpy                 # Numerical operations

# Utilities
json                  # Output formatting
re                    # Text pattern matching
```

---

## NEXT STEPS

After reviewing these recommendations, please specify:
1. Which extraction methods you'd like to implement first
2. Any specific requirements or constraints
3. Preferred output format modifications
4. Target use cases for the micro-course module

