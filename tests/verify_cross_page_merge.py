import sys
import os
import json

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from features.extraction import Extraction


def verify_cross_page():
    print("Running extraction on Page 3 and 4...")
    # Initialize extractor for page 3 and 4
    extractor = Extraction(pages=[3, 4],
                           use_ollama=False,
                           extract_images=False)
    result = extractor.extract()

    # Look for the merged text
    target_start = "In comparative economic analyses"
    target_end = "depends more on the (nominal) GDP per capita"

    found = False
    for page in result['pages']:
        for element in page['elements']:
            content = element['content']
            if target_start in content and target_end in content:
                print("\nSUCCESS: Found merged cross-page text!")
                print(
                    f"Content snippet: ...{content[content.find(target_start):content.find(target_end)+len(target_end)]}..."
                )
                found = True
                break
        if found: break

    # Check for connection metadata
    print("\nChecking for connection metadata...")

    p3_last_para = None
    p3 = [p for p in result['pages'] if p['page_number'] == 3][0]
    for elem in reversed(p3['elements']):
        if elem['type'] == 'paragraph':
            p3_last_para = elem
            break

    p4_first_para = None
    p4 = [p for p in result['pages'] if p['page_number'] == 4][0]
    for elem in p4['elements']:
        if elem['type'] == 'paragraph':
            p4_first_para = elem
            break

    if p3_last_para and p4_first_para:
        print(f"Page 3 Last Para ID: {p3_last_para['id']}")
        print(f"Page 4 First Para ID: {p4_first_para['id']}")

        conn_next = p3_last_para.get('metadata',
                                     {}).get('next_page_connection')
        conn_prev = p4_first_para.get('metadata',
                                      {}).get('prev_page_connection')

        print(f"P3 'next_page_connection': {conn_next}")
        print(f"P4 'prev_page_connection': {conn_prev}")

        if conn_next == p4_first_para['id'] and conn_prev == p3_last_para['id']:
            print("SUCCESS: Paragraphs are linked across pages!")
        else:
            print("FAILURE: Paragraphs are NOT linked.")
    else:
        print("Could not find paragraphs to check.")


if __name__ == "__main__":
    verify_cross_page()
