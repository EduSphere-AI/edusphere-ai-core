# Multilingual Support Guide

## Overview

The PDF extraction module now includes comprehensive multilingual support, automatically detecting languages, writing systems, and text encodings for all extracted content.

## Features

### 1. Automatic Language Detection

Every text block and table cell automatically includes language detection:

```json
{
  "language": {
    "code": "en",
    "name": "English",
    "confidence": 0.98,
    "writing_system": "ltr",
    "encoding": "utf-8"
  }
}
```

### 2. Writing System Detection

The module automatically detects writing systems:

- **LTR (Left-to-Right)**: English, German, French, Spanish, Russian, etc.
- **RTL (Right-to-Left)**: Arabic, Hebrew, Persian, Urdu
- **CJK (Chinese, Japanese, Korean)**: Complex character-based scripts
- **Mixed**: Documents containing multiple writing systems

### 3. Document-Level Language Statistics

The metadata includes comprehensive language information:

```json
{
  "metadata": {
    "languages": [
      {
        "code": "en",
        "name": "English",
        "frequency": 150,
        "percentage": 75.0
      },
      {
        "code": "de",
        "name": "German",
        "frequency": 50,
        "percentage": 25.0
      }
    ],
    "primary_language": "en",
    "writing_systems": [
      {
        "system": "ltr",
        "count": 200,
        "percentage": 100.0
      }
    ]
  }
}
```

## Supported Languages

### European Languages
- English (en)
- German (de)
- French (fr)
- Spanish (es)
- Italian (it)
- Portuguese (pt)
- Dutch (nl)
- Russian (ru)
- Polish (pl)
- Czech (cs)
- Hungarian (hu)
- Romanian (ro)
- Bulgarian (bg)
- Greek (el)
- And more...

### Asian Languages
- Chinese - Simplified (zh-cn)
- Chinese - Traditional (zh-tw)
- Japanese (ja)
- Korean (ko)
- Hindi (hi)
- Thai (th)
- Vietnamese (vi)
- Indonesian (id)
- Malay (ms)
- Tagalog (tl)
- And more...

### Middle Eastern Languages
- Arabic (ar)
- Hebrew (he)
- Persian (fa)
- Turkish (tr)
- Urdu (ur)
- And more...

## Usage Examples

### Basic Usage

```python
from pdf_extractor import PDFExtractor

# Extract from multilingual PDF
extractor = PDFExtractor("multilingual_document.pdf")
data = extractor.extract_all()

# Check primary language
print(f"Primary Language: {data['document']['metadata']['primary_language']}")

# View all detected languages
for lang in data['document']['metadata']['languages']:
    print(f"{lang['name']}: {lang['percentage']}%")
```

### Filter by Language

```python
# Extract only English content blocks
english_blocks = []
for page in data['document']['pages']:
    for block in page['content_blocks']:
        if block['language']['code'] == 'en':
            english_blocks.append(block)
```

### Handle RTL Languages

```python
# Process RTL content blocks
rtl_blocks = []
for page in data['document']['pages']:
    for block in page['content_blocks']:
        if block['language']['writing_system'] == 'rtl':
            rtl_blocks.append(block)
            # Handle RTL-specific processing
            print(f"RTL Block: {block['content']}")
```

### Mixed Language Documents

```python
# Identify mixed language sections
for page in data['document']['pages']:
    current_lang = None
    for block in page['content_blocks']:
        if block['language']['code'] != current_lang:
            print(f"Language switch: {current_lang} -> {block['language']['code']}")
            current_lang = block['language']['code']
```

## Configuration

### Minimum Text Length

Language detection requires a minimum amount of text. Very short text blocks (< 3 characters) may not have reliable language detection.

### Confidence Thresholds

You can filter content by confidence level:

```python
# Only include high-confidence detections
high_confidence_blocks = [
    block for page in data['document']['pages']
    for block in page['content_blocks']
    if block['language']['confidence'] > 0.7
]
```

### Custom Language Detection

If needed, you can modify the `detect_language()` method in `pdf_extractor.py` to:
- Adjust confidence thresholds
- Add custom language mappings
- Implement domain-specific detection

## Writing System Handling

### Left-to-Right (LTR)

Standard processing for most Western languages:
- No special handling required
- Standard text alignment applies

### Right-to-Left (RTL)

For RTL languages like Arabic and Hebrew:
- Writing system is detected automatically
- Text extraction preserves original order
- May require special rendering in frontend

### CJK (Chinese, Japanese, Korean)

For complex character scripts:
- Handles character-based languages
- Detects simplified vs. traditional Chinese
- Supports mixed CJK content

## Encoding Detection

The module automatically detects text encodings:
- UTF-8 (most common)
- ISO-8859-1 (Latin-1)
- Windows-1252
- And other common encodings

Encoding information is stored in each text block for proper handling during recompilation.

## Limitations

1. **Short Text**: Very short text (< 3 characters) may not be reliably detected
2. **Mixed Languages**: Single blocks with mixed languages may default to the predominant language
3. **Code/Technical Content**: Technical terms or code snippets may not be accurately detected
4. **Low Confidence**: Some text may have low confidence scores, requiring manual review

## Best Practices

1. **Review Language Detection**: Check confidence scores, especially for specialized documents
2. **Handle Mixed Documents**: Be aware that multilingual documents will have multiple language codes
3. **Use Writing System Info**: Leverage writing system information for proper text rendering
4. **Validate Primary Language**: Use primary language as a guide, but verify for accuracy-critical applications

## Troubleshooting

### Language Detection Fails

If language detection returns "unknown":
- Text may be too short (< 3 characters)
- Text may contain only numbers or symbols
- Install or update langdetect: `pip install --upgrade langdetect`

### Incorrect Language Detection

If detected language seems incorrect:
- Check confidence score (low = less reliable)
- Text may be mixed or technical
- Consider post-processing with domain-specific rules

### Encoding Issues

If text appears garbled:
- Check the `encoding` field in language object
- Ensure UTF-8 support in your processing pipeline
- Verify PDF source encoding

## Installation

Ensure multilingual libraries are installed:

```bash
pip install langdetect chardet
```

Or install all requirements:

```bash
pip install -r requirements.txt
```

## Examples

See the sample extraction output in `output/extracted_data.json` to see multilingual information in action.

