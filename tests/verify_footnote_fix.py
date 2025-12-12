import sys
import os
import json

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from features.extraction import Extraction


def verify_fix():
    print("Running extraction on Page 3...")
    # Initialize extractor for page 3 only
    extractor = Extraction(pages=[3],
                           use_ollama=False,
                           extract_images=False)
    result = extractor.extract()

    # Find the text
    target_text = "In comparative economic analyses"
    found = False

    for page in result['pages']:
        for element in page['elements']:
            if target_text in element['content']:
                print(f"\nFound element: {element['id']}")
                print(f"Type: {element['type']}")
                print(f"Content: {element['content']}...")

                if element['type'] == 'paragraph':
                    print("SUCCESS: Element is now classified as PARAGRAPH.")
                else:
                    print(
                        f"FAILURE: Element is still classified as {element['type']}."
                    )
                found = True
                break
        if found: break

    if not found:
        print("FAILURE: Could not find the target text.")


if __name__ == "__main__":
    verify_fix()
