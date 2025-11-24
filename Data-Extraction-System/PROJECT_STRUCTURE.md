# Project Structure

## Directory Layout

```
Data-Extraction-System/
│
├── Core Modules
│   ├── pdf_extractor.py              # Main extraction module (950+ lines)
│   ├── view_extracted_data.py        # Statistics viewer
│   └── test_multilingual.py          # Multilingual analysis tool
│
├── Configuration
│   ├── requirements.txt              # Python dependencies
│   └── .gitignore                   # Git ignore patterns
│
├── Documentation
│   ├── README.md                     # Main documentation
│   ├── QUICK_START.md               # Quick start guide
│   ├── PROJECT_STRUCTURE.md         # This file
│   ├── PDF_Extraction_Recommendations.md  # Methodology & recommendations
│   ├── MULTILINGUAL_GUIDE.md        # Multilingual features guide
│   ├── EXTRACTION_SUMMARY.md        # Sample extraction results
│   └── MULTILINGUAL_IMPLEMENTATION_SUMMARY.md  # Implementation details
│
└── Output (generated)
    └── output/
        ├── extracted_data.json      # Extracted data (JSON format)
        └── images/                  # Extracted images/figures
```

## File Descriptions

### Core Modules

#### `pdf_extractor.py`
Main extraction module containing:
- `PDFExtractor` class - Core extraction functionality
- Text extraction with hierarchy detection
- Table extraction with structure preservation
- Image/figure extraction with text overlay separation
- Language detection (50+ languages)
- Writing system detection (LTR, RTL, CJK)
- Encoding detection
- Relationship mapping
- Noise reduction

**Key Methods:**
- `extract_all()` - Main extraction method
- `extract_text_blocks()` - Text extraction with hierarchy
- `extract_tables()` - Table extraction
- `extract_images_and_figures()` - Image/figure extraction
- `detect_language()` - Language detection
- `reduce_noise()` - Header/footer removal

#### `view_extracted_data.py`
Statistics viewer for extracted data:
- Document-level statistics
- Text type distribution
- Hierarchy level analysis
- Sample content blocks

**Usage:** `python3 view_extracted_data.py output/extracted_data.json`

#### `test_multilingual.py`
Multilingual analysis tool:
- Document-level language statistics
- Block-level language distribution
- Confidence analysis
- Language by text type
- Sample blocks per language

**Usage:** `python3 test_multilingual.py output/extracted_data.json`

### Configuration Files

#### `requirements.txt`
Python package dependencies:
- `pymupdf>=1.23.0` - PDF processing
- `pdfplumber>=0.10.0` - Table extraction
- `pillow>=10.0.0` - Image processing
- `langdetect>=1.0.9` - Language detection
- `chardet>=5.0.0` - Encoding detection

#### `.gitignore`
Git ignore patterns for:
- Python cache files
- Virtual environments
- Output files
- Extracted images

### Documentation Files

#### `README.md`
Complete project documentation:
- Features overview
- Installation instructions
- Usage examples
- Output structure
- Extraction methods
- Customization guide

#### `QUICK_START.md`
Quick reference guide:
- Installation steps
- Basic usage
- Common examples
- File structure overview

#### `PDF_Extraction_Recommendations.md`
Methodology and recommendations:
- Extraction methods for each data category
- Library recommendations
- JSON schema design
- Implementation priorities
- Noise reduction strategies

#### `MULTILINGUAL_GUIDE.md`
Comprehensive multilingual features guide:
- Language detection overview
- Writing system detection
- Supported languages
- Usage examples
- Configuration options
- Troubleshooting

#### `EXTRACTION_SUMMARY.md`
Sample extraction results and analysis:
- Statistics from test PDF
- Feature verification
- Notes and observations

#### `MULTILINGUAL_IMPLEMENTATION_SUMMARY.md`
Implementation details:
- Technical implementation
- Test results
- Supported languages
- Limitations and considerations

## Data Flow

```
PDF Input
    ↓
[pdf_extractor.py]
    ↓
    ├──→ Text Blocks (with language detection)
    ├──→ Tables (with structure)
    ├──→ Images/Figures (with metadata)
    └──→ Metadata (document-level)
    ↓
Structured JSON Output
    ↓
[view_extracted_data.py] or [test_multilingual.py]
    ↓
Analysis & Statistics
```

## Output Format

The extraction produces a structured JSON file:

```json
{
  "document": {
    "metadata": {
      "title": "...",
      "author": "...",
      "languages": [...],
      "primary_language": "...",
      "writing_systems": [...]
    },
    "pages": [
      {
        "page_number": 1,
        "dimensions": {...},
        "content_blocks": [...],
        "tables": [...],
        "images": [...],
        "figures": [...]
      }
    ]
  }
}
```

## Usage Workflow

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Extract PDF**
   ```bash
   python3 pdf_extractor.py input.pdf output
   ```

3. **View Results**
   ```bash
   python3 view_extracted_data.py output/extracted_data.json
   python3 test_multilingual.py output/extracted_data.json
   ```

4. **Process JSON**
   - Use extracted JSON for micro-course transformation
   - Leverage language information for multilingual support
   - Use relationships for content organization

## Dependencies

- **Python 3.7+** required
- All dependencies listed in `requirements.txt`
- No external services required (all processing is local)

## Extension Points

The system can be extended:

1. **Custom Language Detection**: Modify `detect_language()` method
2. **Additional Extractors**: Add methods to `PDFExtractor` class
3. **Output Formats**: Extend `save_json()` for other formats
4. **Post-Processing**: Add custom processing methods
5. **Database Integration**: Add database storage methods

