import json
import os
from collections import defaultdict


def check_generation_duplicates():
    base_dir = os.path.join(os.path.dirname(__file__), "..")
    file_path = os.path.join(base_dir, "output", "generation",
                             "presentation.json")

    if not os.path.exists(file_path):
        print(f"Error: File not found at {file_path}")
        return

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error reading JSON: {e}")
        return

    all_slides = data.get("introduction", []) + data.get("slides", [])

    print(f"Total slides found: {len(all_slides)}")

    # 1. Check for Duplicate Slide Titles (excluding generic ones like 'Review & Assessment')
    title_counts = defaultdict(list)
    for i, slide in enumerate(all_slides):
        title = slide.get("slide_title", "").strip()
        if title and title != "Review & Assessment":
            title_counts[title].append(i + 1)  # 1-based index

    duplicate_titles = {k: v for k, v in title_counts.items() if len(v) > 1}

    if duplicate_titles:
        print("\n[!] Duplicate Slide Titles Found:")
        for title, indices in duplicate_titles.items():
            print(f"  - '{title}' appears on slides: {indices}")
    else:
        print("\n[+] No duplicate slide titles found.")

    # 2. Check for Duplicate Content Blocks (> 30 chars to avoid common short phrases)
    content_counts = defaultdict(list)
    for i, slide in enumerate(all_slides):
        content_blocks = slide.get("content", [])
        for block in content_blocks:
            text = block.get("text", "").strip()
            if len(text) > 30:
                content_counts[text].append(i + 1)

    duplicate_content = {k: v for k, v in content_counts.items() if len(v) > 1}

    if duplicate_content:
        print("\n[!] Duplicate Content Blocks Found (>30 chars):")
        for text, indices in duplicate_content.items():
            preview = text[:60] + "..." if len(text) > 60 else text
            print(f"  - '{preview}' appears on slides: {indices}")
    else:
        print("\n[+] No duplicate content blocks found.")


if __name__ == "__main__":
    check_generation_duplicates()
