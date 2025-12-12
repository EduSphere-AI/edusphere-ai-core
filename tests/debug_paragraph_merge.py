#!/usr/bin/env python3
"""
Debug script to analyze paragraph merging behavior across pages.
"""

import json
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import settings


def analyze_paragraphs():
    extraction_file = os.path.join(settings.extraction_output_path,
                                   "extraction_result.json")
    with open(extraction_file, "r") as f:
        data = json.load(f)

    print("=" * 80)
    print("PARAGRAPH ANALYSIS BY PAGE")
    print("=" * 80)

    for page in data["pages"]:
        page_num = page["page_number"]
        elements = page.get("elements", [])

        # Count consecutive paragraphs
        consecutive_paras = []
        current_run = []

        for elem in elements:
            if elem.get("type") == "paragraph":
                current_run.append(elem)
            else:
                if len(current_run) > 1:
                    consecutive_paras.append(current_run)
                current_run = []

        if len(current_run) > 1:
            consecutive_paras.append(current_run)

        if consecutive_paras:
            print(f"\n--- Page {page_num} ---")
            for run_idx, run in enumerate(consecutive_paras):
                print(
                    f"\n  Consecutive paragraph group {run_idx + 1} ({len(run)} paragraphs):"
                )
                for i, para in enumerate(run):
                    content = para.get("content", "")
                    preview = content[:80] + "..." if len(
                        content) > 80 else content
                    ends_with = content[-30:] if len(content) > 30 else content
                    print(f"    [{i+1}] Starts: {preview}")
                    print(f"        Ends: ...{ends_with}")
                    print()

    print("\n" + "=" * 80)
    print("SUMMARY: Pages with consecutive paragraphs that could be merged")
    print("=" * 80)


if __name__ == "__main__":
    analyze_paragraphs()
