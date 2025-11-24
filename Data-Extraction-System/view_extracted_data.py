#!/usr/bin/env python3
"""
Quick viewer for extracted PDF data
Useful for verifying extraction results
"""

import json
import sys
from collections import Counter

def view_extraction_stats(json_path):
    """Display statistics about extracted data"""
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    doc = data['document']
    metadata = doc['metadata']
    pages = doc['pages']
    
    print("=" * 60)
    print("PDF EXTRACTION STATISTICS")
    print("=" * 60)
    print(f"\nDocument: {metadata['source_file']}")
    print(f"Title: {metadata.get('title', 'N/A')}")
    print(f"Author: {metadata.get('author', 'N/A')}")
    print(f"Pages: {metadata['page_count']}")
    print()
    
    # Text statistics
    total_blocks = 0
    text_types = Counter()
    hierarchy_levels = Counter()
    
    total_tables = 0
    total_images = 0
    total_figures = 0
    
    for page in pages:
        total_blocks += len(page['content_blocks'])
        total_tables += len(page['tables'])
        total_images += len(page['images'])
        total_figures += len(page['figures'])
        
        for block in page['content_blocks']:
            text_types[block['text_type']] += 1
            hierarchy_levels[block['hierarchy_level']] += 1
    
    print("TEXT EXTRACTION:")
    print(f"  Total Content Blocks: {total_blocks}")
    print("\n  Text Type Distribution:")
    for text_type, count in sorted(text_types.items(), key=lambda x: -x[1]):
        print(f"    {text_type:15s}: {count:3d}")
    
    print("\n  Hierarchy Level Distribution:")
    for level in sorted(hierarchy_levels.keys()):
        print(f"    Level {level}: {hierarchy_levels[level]} blocks")
    
    print(f"\nTABLES: {total_tables}")
    if total_tables > 0:
        for page in pages:
            if page['tables']:
                for table in page['tables']:
                    print(f"  Page {page['page_number']}: "
                          f"{table['structure']['rows']} rows × "
                          f"{table['structure']['columns']} columns")
    
    print(f"\nIMAGES: {total_images}")
    print(f"FIGURES: {total_figures}")
    
    print("\n" + "=" * 60)
    print("\nSample Content Blocks (First Page):")
    print("-" * 60)
    
    if pages:
        first_page = pages[0]
        print(f"\nPage {first_page['page_number']} "
              f"({len(first_page['content_blocks'])} blocks):\n")
        
        for i, block in enumerate(first_page['content_blocks'][:10]):
            print(f"{i+1}. [{block['text_type'].upper():12s}] "
                  f"Level {block['hierarchy_level']}")
            content = block['content'][:80]
            if len(block['content']) > 80:
                content += "..."
            print(f"   {content}")
            if block['parent_id']:
                print(f"   Parent: {block['parent_id']}")
            if block['children_ids']:
                print(f"   Children: {len(block['children_ids'])}")
            print()


if __name__ == "__main__":
    json_path = sys.argv[1] if len(sys.argv) > 1 else "output/extracted_data.json"
    view_extraction_stats(json_path)

