"""
run_microcourse_from_json.py
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .json_microcourse import (
    load_extraction_result,
    build_microcourse_from_json,
    microcourse_to_dict,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build micro-course (slides + questions) from extraction_result.json"
    )
    parser.add_argument(
        "input_json",
        type=str,
        help="Path to extraction_result.json produced by the PDF extractor",
    )
    parser.add_argument(
        "output_json",
        type=str,
        help="Where to write the microcourse JSON with slides and learn controls",
    )
    args = parser.parse_args()

    input_path = Path(args.input_json)
    output_path = Path(args.output_json)

    doc = load_extraction_result(input_path)
    microcourse = build_microcourse_from_json(doc)
    out_dict = microcourse_to_dict(microcourse)

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(out_dict, f, ensure_ascii=False, indent=2)

    print(f"Microcourse written to: {output_path}")


if __name__ == "__main__":
    main()