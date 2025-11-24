#!/usr/bin/env python3
"""
Test script to verify multilingual extraction features
"""

import json
import sys
from collections import Counter, defaultdict

def analyze_multilingual_data(json_path):
    """Analyze multilingual aspects of extracted data"""
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    doc = data['document']
    metadata = doc['metadata']
    pages = doc['pages']
    
    print("=" * 70)
    print("MULTILINGUAL EXTRACTION ANALYSIS")
    print("=" * 70)
    
    # Document-level statistics
    print("\n📊 DOCUMENT-LEVEL LANGUAGE STATISTICS")
    print("-" * 70)
    print(f"Primary Language: {metadata.get('primary_language', 'N/A')}")
    
    if metadata.get('languages'):
        print("\nDetected Languages:")
        for lang in metadata['languages']:
            print(f"  • {lang['name']:20s} ({lang['code']:5s}): {lang['frequency']:4d} blocks ({lang['percentage']:5.2f}%)")
    else:
        print("  No languages detected")
    
    if metadata.get('writing_systems'):
        print("\nWriting Systems:")
        for ws in metadata['writing_systems']:
            print(f"  • {ws['system'].upper():10s}: {ws['count']:4d} blocks ({ws['percentage']:5.2f}%)")
    
    # Block-level language analysis
    print("\n📝 BLOCK-LEVEL LANGUAGE DISTRIBUTION")
    print("-" * 70)
    
    all_languages = []
    all_writing_systems = []
    language_by_type = defaultdict(Counter)
    confidence_scores = []
    
    for page in pages:
        for block in page['content_blocks']:
            lang = block.get('language', {})
            lang_code = lang.get('code', 'unknown')
            lang_name = lang.get('name', 'Unknown')
            confidence = lang.get('confidence', 0)
            writing_system = lang.get('writing_system', 'unknown')
            text_type = block.get('text_type', 'unknown')
            
            all_languages.append(lang_code)
            all_writing_systems.append(writing_system)
            language_by_type[text_type][lang_code] += 1
            confidence_scores.append(confidence)
    
    lang_counter = Counter(all_languages)
    ws_counter = Counter(all_writing_systems)
    
    print(f"Total Text Blocks Analyzed: {len(all_languages)}")
    print(f"\nLanguage Distribution:")
    for lang_code, count in lang_counter.most_common(10):
        percentage = (count / len(all_languages)) * 100
        print(f"  • {lang_code:5s}: {count:4d} blocks ({percentage:5.2f}%)")
    
    print(f"\nWriting System Distribution:")
    for ws, count in ws_counter.most_common():
        percentage = (count / len(all_writing_systems)) * 100
        print(f"  • {ws.upper():10s}: {count:4d} blocks ({percentage:5.2f}%)")
    
    if confidence_scores:
        avg_confidence = sum(confidence_scores) / len(confidence_scores)
        high_confidence = sum(1 for c in confidence_scores if c > 0.8)
        print(f"\nConfidence Statistics:")
        print(f"  • Average Confidence: {avg_confidence:.3f}")
        print(f"  • High Confidence (>0.8): {high_confidence}/{len(confidence_scores)} ({high_confidence/len(confidence_scores)*100:.1f}%)")
    
    # Language by text type
    print("\n📋 LANGUAGE BY TEXT TYPE")
    print("-" * 70)
    for text_type in sorted(language_by_type.keys()):
        counter = language_by_type[text_type]
        total = sum(counter.values())
        print(f"\n{text_type.upper()}: {total} blocks")
        for lang_code, count in counter.most_common(5):
            percentage = (count / total) * 100
            print(f"  • {lang_code:5s}: {count:3d} ({percentage:5.1f}%)")
    
    # Sample blocks from different languages
    print("\n📄 SAMPLE BLOCKS BY LANGUAGE")
    print("-" * 70)
    
    samples_by_lang = defaultdict(list)
    for page in pages:
        for block in page['content_blocks']:
            lang_code = block.get('language', {}).get('code', 'unknown')
            if len(samples_by_lang[lang_code]) < 3:
                samples_by_lang[lang_code].append(block)
    
    for lang_code in sorted(samples_by_lang.keys()):
        if lang_code != 'unknown':
            print(f"\n{lang_code.upper()} Examples:")
            for i, block in enumerate(samples_by_lang[lang_code][:3], 1):
                content = block['content'][:70]
                if len(block['content']) > 70:
                    content += "..."
                confidence = block['language']['confidence']
                print(f"  {i}. [{confidence:.2f}] {content}")
    
    # Table language analysis
    print("\n📊 TABLE LANGUAGE ANALYSIS")
    print("-" * 70)
    
    table_languages = Counter()
    total_table_cells = 0
    
    for page in pages:
        for table in page.get('tables', []):
            for cell in table.get('data', []):
                if 'language' in cell:
                    lang_code = cell['language'].get('code', 'unknown')
                    table_languages[lang_code] += 1
                    total_table_cells += 1
    
    if total_table_cells > 0:
        print(f"Total Table Cells Analyzed: {total_table_cells}")
        print("Language Distribution in Tables:")
        for lang_code, count in table_languages.most_common(10):
            percentage = (count / total_table_cells) * 100
            print(f"  • {lang_code:5s}: {count:4d} cells ({percentage:5.2f}%)")
    else:
        print("  No tables found")
    
    print("\n" + "=" * 70)
    print("Analysis Complete!")
    print("=" * 70)


if __name__ == "__main__":
    json_path = sys.argv[1] if len(sys.argv) > 1 else "output/extracted_data.json"
    analyze_multilingual_data(json_path)

