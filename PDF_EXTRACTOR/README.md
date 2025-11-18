# PDF Content Extractor

A Python package for extracting and standardizing content from academic PDFs without using OCR. Extracts tables, charts, images, and text in a structured format suitable for building multilingual micro-courses.

## Features

- **Table Extraction**: Detects and extracts tables using vector-based layout detection
- **Chart Extraction**: Extracts charts using geometry and text parsing (Option A)
- **Image Extraction**: Extracts raster images with associated labels and embedded text
- **Text Extraction**: Categorizes text into titles, subtitles, body text, and citations
- **No OCR Required**: Works only with embedded PDF content

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Basic Usage

```python
from pdf_extractor import PDFExtractor

# Initialize extractor
extractor = PDFExtractor()

# Extract content from PDF
result = extractor.extract("path/to/document.pdf")

# Output is automatically saved as <document_name>_extracted.json
```

### Custom Output Path

```python
extractor = PDFExtractor()
result = extractor.extract("document.pdf", output_path="output/custom_name.json")
```

### Command Line Usage

```bash
python example_usage.py path/to/document.pdf
```

Or with custom output:

```bash
python example_usage.py path/to/document.pdf output/custom_output.json
```

## Output Format

The extractor generates a JSON file with the following structure:

```json
{
  "document_id": "document_name",
  "source_file": "document.pdf",
  "extraction_date": "2024-01-01T12:00:00",
  "total_pages": 10,
  "pages": [
    {
      "page_number": 1,
      "tables": [
        {
          "table_id": "table_1",
          "bbox": {...},
          "num_rows": 5,
          "num_cols": 3,
          "structure": [[...], [...]],
          "validation": {...}
        }
      ],
      "charts": [
        {
          "figure_id": "figure_1",
          "bbox": {...},
          "title": "...",
          "axis_labels": [...],
          "legend": [...],
          "caption": "..."
        }
      ],
      "images": [
        {
          "image_id": "image_1",
          "bbox": {...},
          "width": 800,
          "height": 600,
          "label": "Figure 1",
          "embedded_text": [...]
        }
      ],
      "text": {
        "titles": [...],
        "subtitles": [...],
        "body": [...],
        "citations": [...]
      }
    }
  ]
}
```

## Module Structure

- `extractor.py`: Main orchestrator class
- `table_extractor.py`: Table detection and extraction
- `chart_extractor.py`: Chart extraction using geometry + text parsing
- `image_extractor.py`: Image extraction with label association
- `text_extractor.py`: Text extraction with ML-based categorization
- `utils.py`: Shared utility functions

## Requirements

- PyMuPDF (fitz) >= 1.23.0
- pdfminer.six >= 20221105
- scikit-learn >= 1.3.0
- numpy >= 1.24.0

## Notes

- The extractor works without OCR, using only embedded PDF content
- Text within tables, charts, and images is excluded from main text extraction
- Chart extraction uses Option A (Geometry + Text Parsing) as specified
- Text categorization uses a combination of heuristics and ML-based classification

