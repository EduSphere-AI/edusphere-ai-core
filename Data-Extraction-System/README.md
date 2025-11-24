# PDF Data Extraction Module

A comprehensive PDF extraction tool that transforms PDF content into structured JSON format for micro-course transformation. This module extracts text, tables, images, and figures while preserving hierarchy, relationships, and styling information.

## Features

✅ **Text Extraction with Hierarchy Detection**

- Automatic classification: title, heading, subheading, paragraph, caption, footnote, author, metadata
- Font size and weight analysis
- Parent-child relationship mapping
- Reading order preservation

✅ **Multilingual Support**

- Automatic language detection for all text blocks
- Support for 50+ languages (ISO 639-1)
- Writing system detection (LTR, RTL, CJK, Mixed)
- Encoding detection and handling
- Language statistics and document analysis

✅ **Table Extraction**

- Structured table data with row/column indices
- Header row detection
- Cell content extraction
- Bounding box coordinates

✅ **Image & Figure Extraction**

- Image extraction with metadata
- Text overlay separation
- Caption association
- Relative positioning

✅ **Noise Reduction**

- Automatic header/footer removal
- Text cleaning and normalization
- Duplicate detection

✅ **Structured JSON Output**

- Complete document structure
- Relationship mapping
- Styling information
- Position coordinates

## Installation

1. Install required dependencies:

```bash
pip install -r requirements.txt
```

Or install manually:

```bash
pip install pymupdf pdfplumber pillow langdetect chardet
```

## Usage

### Basic Usage

```bash
python3 pdf_extractor.py <pdf_path> [output_directory]
```

Example:

```bash
python3 pdf_extractor.py dwr-25-40-2.pdf output
```

### Python API

```python
from pdf_extractor import PDFExtractor

# Initialize extractor
extractor = PDFExtractor("document.pdf", output_dir="output")

# Extract all data
data = extractor.extract_all()

# Save to JSON
extractor.save_json(data, "extracted_data.json")
```

### View Extraction Results

```bash
python3 view_extracted_data.py output/extracted_data.json
```

## Output Structure

The extraction produces a JSON file with the following structure:

```json
{
  "document": {
    "metadata": {
      "title": "...",
      "author": "...",
      "creation_date": "...",
      "page_count": 8,
      "source_file": "...",
      "languages": [
        {
          "code": "en",
          "name": "English",
          "frequency": 200,
          "percentage": 85.5
        }
      ],
      "primary_language": "en",
      "writing_systems": [
        {
          "system": "ltr",
          "count": 234,
          "percentage": 94.7
        }
      ]
    },
    "pages": [
      {
        "page_number": 1,
        "dimensions": {"width": 595.28, "height": 841.89},
        "content_blocks": [...],
        "tables": [...],
        "images": [...],
        "figures": [...]
      }
    ]
  }
}
```

### Content Block Structure

Each text block includes:

- `id`: Unique identifier
- `type`: "text"
- `hierarchy_level`: 1-7 (title to footnote)
- `text_type`: title, heading, paragraph, etc.
- `content`: Extracted text
- `language`: Language information object:
  - `code`: ISO 639-1 language code (e.g., "en", "de", "ar", "zh")
  - `name`: Full language name (e.g., "English", "German", "Arabic", "Chinese")
  - `confidence`: Detection confidence (0.0-1.0)
  - `writing_system`: Writing direction/system ("ltr", "rtl", "cjk", "mixed")
  - `encoding`: Detected text encoding
- `position`: Bounding box coordinates (x0, y0, x1, y1)
- `styling`: Font size, weight, alignment
- `parent_id`: Parent block ID (for hierarchy)
- `children_ids`: List of child block IDs
- `relationships`: Links to figures, tables, footnotes

### Table Structure

Each table includes:

- `id`: Unique identifier
- `caption`: Associated caption text
- `position`: Bounding box coordinates
- `structure`: Rows, columns, header information
- `data`: Array of cell data with row/column indices
  - Each cell includes `language` object with detected language information

### Image/Figure Structure

Each image/figure includes:

- `id`: Unique identifier
- `type`: chart, diagram, photograph, logo
- `caption`: Associated caption
- `position`: Bounding box coordinates
- `file_path`: Path to extracted image file
- `embedded_text`: Text overlays with positions

## Multilingual Support

The extraction module automatically detects language for all text content:

### Supported Features

1. **Language Detection**

   - Automatic detection using Google's langdetect library
   - Supports 50+ languages (ISO 639-1 codes)
   - Confidence scoring for each detection
   - Per-block and document-level statistics

2. **Writing System Detection**

   - **LTR** (Left-to-Right): Latin, Cyrillic, Greek, etc.
   - **RTL** (Right-to-Left): Arabic, Hebrew, Persian, Urdu, etc.
   - **CJK** (Chinese, Japanese, Korean): Complex character sets
   - **Mixed**: Documents with multiple writing systems

3. **Encoding Detection**

   - Automatic character encoding detection
   - UTF-8 handling with fallback
   - Support for various text encodings

4. **Document Analysis**
   - Primary language identification
   - Language frequency statistics
   - Writing system distribution
   - Multi-language document support

### Supported Languages

The module supports major languages including:

- **European**: English, German, French, Spanish, Italian, Portuguese, Dutch, Russian, Polish, Czech, etc.
- **Asian**: Chinese (Simplified/Traditional), Japanese, Korean, Hindi, Thai, Vietnamese, Indonesian, etc.
- **Middle Eastern**: Arabic, Hebrew, Persian, Turkish, Urdu, etc.
- **And many more**: See [langdetect supported languages](https://github.com/Mimino666/langdetect)

### Example Usage

```python
from pdf_extractor import PDFExtractor

extractor = PDFExtractor("multilingual_document.pdf")
data = extractor.extract_all()

# Access language information
for page in data['document']['pages']:
    for block in page['content_blocks']:
        lang = block['language']
        print(f"Text: {block['content'][:50]}")
        print(f"Language: {lang['name']} ({lang['code']})")
        print(f"Confidence: {lang['confidence']}")
        print(f"Writing System: {lang['writing_system']}")

# Document-level language statistics
metadata = data['document']['metadata']
print(f"Primary Language: {metadata['primary_language']}")
print(f"All Languages: {[l['code'] for l in metadata['languages']]}")
```

## Extraction Methods

### Text Extraction

- **Primary Library:** PyMuPDF (fitz)
- **Method:** Font analysis and positioning
- **Hierarchy Detection:** Font size ratios, weight, position
- **Language Detection:** Automatic per-block language identification

### Table Extraction

- **Primary Library:** pdfplumber
- **Method:** Layout analysis and text alignment
- **Header Detection:** Heuristic-based (first row analysis)
- **Language Detection:** Per-cell language detection

### Image Extraction

- **Primary Library:** PyMuPDF (fitz)
- **Method:** Direct image extraction from PDF objects
- **Text Overlay:** Proximity-based text detection

## Limitations

1. **Vector Graphics**: PDFs with vector graphics (SVG paths) may not extract as standard images
2. **Complex Layouts**: Very complex multi-column layouts may require post-processing
3. **Merged Table Cells**: Some merged cells may not be fully preserved
4. **OCR**: No OCR is used (as per requirements) - only native PDF text extraction

## File Structure

```
.
├── pdf_extractor.py          # Main extraction module
├── view_extracted_data.py    # Statistics viewer
├── requirements.txt          # Python dependencies
├── PDF_Extraction_Recommendations.md  # Method recommendations
├── EXTRACTION_SUMMARY.md     # Extraction results summary
├── README.md                 # This file
└── output/                   # Output directory
    ├── extracted_data.json   # Extracted JSON data
    └── images/               # Extracted images
```

## Example Results

From the sample PDF (`dwr-25-40-2.pdf`):

- **247 content blocks** extracted
- **6 tables** identified and extracted
- **8 pages** processed
- **Text hierarchy** fully mapped
- **Relationships** preserved

## Customization

### Adjusting Text Classification

Modify the `classify_text_type()` method in `pdf_extractor.py` to adjust:

- Font size thresholds
- Position-based detection
- Pattern matching for special text types

### Table Extraction Settings

Modify the `extract_tables()` method to adjust:

- Table detection sensitivity
- Header row detection heuristics
- Cell extraction rules

### Image Extraction Settings

Modify the `extract_images_and_figures()` method to adjust:

- Size thresholds for figure classification
- Text overlay proximity detection
- Image format handling

## Troubleshooting

### No Images Extracted

- PDF may contain vector graphics instead of raster images
- Consider converting pages to images first
- Check PDF structure with: `pdfinfo document.pdf`

### Table Detection Issues

- Complex layouts may require manual adjustment
- Try different extraction settings
- Check table structure in pdfplumber directly

### Text Hierarchy Issues

- Font statistics are calculated per-page
- Very varied font sizes may affect classification
- Adjust thresholds in `classify_text_type()`

## License

This module is provided as-is for PDF extraction purposes.

## Support

For issues or questions, review:

- `PDF_Extraction_Recommendations.md` for methodology
- `EXTRACTION_SUMMARY.md` for results analysis
- Code comments in `pdf_extractor.py` for implementation details
