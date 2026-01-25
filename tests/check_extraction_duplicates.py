import json
import os
from collections import defaultdict


def check_extraction_duplicates():
    base_dir = os.path.join(os.path.dirname(__file__), "..")
    file_path = os.path.join(base_dir, "output", "extraction",
                             "extraction_result.json")

    if not os.path.exists(file_path):
        print(f"Error: File not found at {file_path}")
        return

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error reading JSON: {e}")
        return

    pages = data.get("pages", [])
    if not pages:
        print("No pages found in extraction result.")
        return

    all_elements = []
    for page in pages:
        if "elements" in page:
            all_elements.extend(page["elements"])

    print(f"Total extracted elements: {len(all_elements)}")

    # 1. Check for Duplicate IDs
    id_counts = defaultdict(int)
    for elem in all_elements:
        if 'id' in elem:
            id_counts[elem['id']] += 1

    duplicate_ids = {k: v for k, v in id_counts.items() if v > 1}

    if duplicate_ids:
        print(f"\n[!] Found {len(duplicate_ids)} duplicate IDs:")
        # Show first 5
        for k, v in list(duplicate_ids.items())[:5]:
            print(f"  - ID {k}: {v} occurrences")
    else:
        print("\n[+] No duplicate IDs found.")

    # 2. Check for Duplicate Content (> 20 chars)
    content_counts = defaultdict(list)
    for elem in all_elements:
        content = elem.get('content', '').strip()
        if len(content) > 20:
            content_counts[content].append(elem.get('id', 'unknown'))

    duplicate_content = {k: v for k, v in content_counts.items() if len(v) > 1}

    if duplicate_content:
        print(
            f"\n[!] Found {len(duplicate_content)} duplicate content blocks (>20 chars):"
        )
        for content, ids in duplicate_content.items():
            preview = content[:60].replace('\n', ' ') + "..."
            print(
                f"  - '{preview}': {len(ids)} occurrences (IDs: {ids[:3]}...)")
    else:
        print("\n[+] No duplicate content blocks found.")


if __name__ == "__main__":
    check_extraction_duplicates()
