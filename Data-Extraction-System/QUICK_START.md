# Quick Start Guide

## Installation

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

Or install manually:
```bash
pip install pymupdf pdfplumber pillow langdetect chardet
```

## Basic Usage

### Extract from a PDF

```bash
python3 pdf_extractor.py <pdf_path> [output_directory]
```

Example:
```bash
python3 pdf_extractor.py ../Downloads/document.pdf output
```

### View Extraction Statistics

```bash
python3 view_extracted_data.py output/extracted_data.json
```

### Analyze Multilingual Content

```bash
python3 test_multilingual.py output/extracted_data.json
```

## Python API Usage

```python
from pdf_extractor import PDFExtractor

# Initialize extractor
extractor = PDFExtractor("path/to/document.pdf", output_dir="output")

# Extract all data
data = extractor.extract_all()

# Save to JSON
extractor.save_json(data, "extracted_data.json")

# Access language information
print(f"Primary Language: {data['document']['metadata']['primary_language']}")

# Access extracted content
for page in data['document']['pages']:
    for block in page['content_blocks']:
        print(f"{block['text_type']}: {block['content'][:50]}")
        print(f"Language: {block['language']['name']} ({block['language']['code']})")
```

## File Structure

```
Data-Extraction-System/
├── pdf_extractor.py              # Main extraction module
├── view_extracted_data.py        # Statistics viewer
├── test_multilingual.py          # Multilingual analysis tool
├── requirements.txt              # Python dependencies
├── README.md                     # Complete documentation
├── QUICK_START.md               # This file
├── PDF_Extraction_Recommendations.md  # Methodology guide
├── MULTILINGUAL_GUIDE.md        # Multilingual features guide
├── EXTRACTION_SUMMARY.md        # Sample extraction results
├── MULTILINGUAL_IMPLEMENTATION_SUMMARY.md  # Implementation details
├── .gitignore                   # Git ignore file
└── output/                      # Output directory (created on first run)
    ├── extracted_data.json      # Extracted data
    └── images/                  # Extracted images
```

## Features

✅ **Text Extraction** with hierarchy detection
✅ **Table Extraction** with structure preservation
✅ **Image/Figure Extraction** with text overlay separation
✅ **Multilingual Support** with automatic language detection
✅ **Writing System Detection** (LTR, RTL, CJK)
✅ **Noise Reduction** and data cleaning
✅ **Structured JSON Output** for micro-course transformation

## Next Steps

1. Read `README.md` for complete documentation
2. Check `MULTILINGUAL_GUIDE.md` for multilingual features
3. Review `PDF_Extraction_Recommendations.md` for methodology details
4. See `EXTRACTION_SUMMARY.md` for sample results

## Support

For issues or questions:
- Review the documentation files
- Check code comments in `pdf_extractor.py`
- Verify all dependencies are installed correctly

