#!/usr/bin/env python3
"""
Vision Model Comparison Script
Tests multiple Ollama vision models on the same chart image to compare accuracy.
"""

import os
import sys
import json
import base64
import time
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ollama
from PIL import Image
from io import BytesIO

from config import settings

# Models to test (excluding 34b - too slow for practical use)
VISION_MODELS = [
    "llava:v1.6",  # Improved version  
    "llava-llama3",  # Llama3 based
    "minicpm-v",  # Document specialized
    "llama3.2-vision",  # Llama 3.2 vision
]

# The ground truth for the chart (approximate values read manually)
GROUND_TRUTH = """
Chart: "The gap between the rich and poor states is widening more and more"
Type: Grouped bar chart comparing 2025 vs 2070
Y-axis: Tax revenue per capita as percentage of national average (0-150)
X-axis: German state codes

Approximate values for 2025 (blue bars, left group):
- BY (Bavaria): ~140
- HE (Hesse): ~125  
- BW (Baden-Württemberg): ~105
- NW (North Rhine-Westphalia): ~95
- RP (Rhineland-Palatinate): ~90
- SH (Schleswig-Holstein): ~85
- NI (Lower Saxony): ~80
- BB (Brandenburg): ~70
- SL (Saarland): ~65
- SN (Saxony): ~60
- MV (Mecklenburg-Vorpommern): ~55
- ST (Saxony-Anhalt): ~45
- TH (Thuringia): ~40

Approximate values for 2070 (pink bars, right group):
- BY: ~145
- HE: ~130
- BW: ~100
- BB: ~90
- SH: ~85
- SN: ~80
- NW: ~75
- RP: ~70
- MV: ~70
- ST: ~65
- NI: ~60
- TH: ~55
- SL: ~50

Also includes a map of Germany showing donor (blue) vs recipient (pink) states.
"""

ANALYSIS_PROMPT = """Analyze this chart from a German fiscal policy document carefully.

IMPORTANT: Read the actual values from the chart as accurately as possible.

This appears to be a bar chart about fiscal capacity of German federal states. Please:
1. Identify the chart title
2. Describe what the x-axis and y-axis represent
3. Read the approximate value for EACH bar you can see
4. Note if there are grouped bars (e.g., comparing different years)
5. List all German state abbreviations you can see (like BY, HE, BW, etc.)

Provide your analysis in JSON format:
{
    "title": "the chart title",
    "chart_type": "bar|grouped_bar|stacked_bar|line|other",
    "description": "what the chart shows",
    "axes": {
        "x_axis": "what x-axis represents",
        "y_axis": "what y-axis represents with scale"
    },
    "data_points": [
        {"state": "BY", "value_2025": 140, "value_2070": 145},
        {"state": "HE", "value_2025": 125, "value_2070": 130}
    ],
    "states_identified": ["BY", "HE", "BW", ...],
    "key_insight": "main trend or message"
}

Be as precise as possible when reading the bar heights. Return ONLY the JSON object."""


def get_available_models():
    """Check which models are available locally."""
    try:
        # Use subprocess as it's more reliable
        import subprocess
        result = subprocess.run(['ollama', 'list'],
                                capture_output=True,
                                text=True)
        lines = result.stdout.strip().split('\n')[1:]  # Skip header
        available_full = []
        for line in lines:
            if line.strip():
                name = line.split()[0]
                available_full.append(name)
        available = [n.split(':')[0] for n in available_full]
        return available, available_full
    except Exception as e:
        print(f"Error listing models: {e}")
        return [], []


def load_image_as_base64(image_path: str) -> str:
    """Load image and convert to base64."""
    with open(image_path, 'rb') as f:
        return base64.b64encode(f.read()).decode('utf-8')


def test_model(model_name: str, image_base64: str) -> dict:
    """Test a single model and return results."""
    print(f"\n{'='*60}")
    print(f"Testing model: {model_name}")
    print('=' * 60)

    result = {
        "model": model_name,
        "success": False,
        "time_seconds": 0,
        "response": None,
        "parsed_json": None,
        "error": None
    }

    try:
        start_time = time.time()

        response = ollama.generate(model=model_name,
                                   prompt=ANALYSIS_PROMPT,
                                   images=[image_base64],
                                   stream=False)

        elapsed = time.time() - start_time
        result["time_seconds"] = round(elapsed, 2)
        result["response"] = response.get("response", "")

        # Try to parse JSON from response
        response_text = result["response"]

        # Find JSON in response
        import re
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            try:
                result["parsed_json"] = json.loads(json_match.group(0))
                result["success"] = True
            except json.JSONDecodeError:
                result["error"] = "Failed to parse JSON"
        else:
            result["error"] = "No JSON found in response"

        print(f"✓ Completed in {elapsed:.2f}s")

    except Exception as e:
        result["error"] = str(e)
        print(f"✗ Error: {e}")

    return result


def evaluate_result(result: dict) -> dict:
    """Evaluate the quality of the extraction."""
    evaluation = {"score": 0, "max_score": 100, "details": []}

    if not result.get("parsed_json"):
        evaluation["details"].append("No valid JSON output")
        return evaluation

    data = result["parsed_json"]

    # Check for chart title (10 points)
    if data.get("title"):
        if "gap" in data["title"].lower() or "fiscal" in data["title"].lower():
            evaluation["score"] += 10
            evaluation["details"].append("✓ Title correctly identified (+10)")
        else:
            evaluation["score"] += 5
            evaluation["details"].append(
                "~ Title present but may be inaccurate (+5)")

    # Check for chart type (10 points)
    chart_type = data.get("chart_type", "").lower()
    if "grouped" in chart_type or "bar" in chart_type:
        evaluation["score"] += 10
        evaluation["details"].append(
            "✓ Chart type identified as bar/grouped (+10)")

    # Check for axes (10 points)
    axes = data.get("axes", {})
    if axes.get("y_axis") and ("150" in str(axes["y_axis"])
                               or "percent" in str(axes["y_axis"]).lower()):
        evaluation["score"] += 10
        evaluation["details"].append("✓ Y-axis scale identified (+10)")
    elif axes.get("y_axis"):
        evaluation["score"] += 5
        evaluation["details"].append("~ Y-axis present but scale unclear (+5)")

    # Check for state identification (20 points)
    states = data.get("states_identified", [])
    if not states:
        # Try to extract from data_points
        states = [
            dp.get("state", dp.get("label", ""))
            for dp in data.get("data_points", [])
        ]

    expected_states = [
        "BY", "HE", "BW", "NW", "RP", "SH", "NI", "BB", "SL", "SN", "MV", "ST",
        "TH"
    ]
    found_states = [s for s in states if s in expected_states]

    if len(found_states) >= 10:
        evaluation["score"] += 20
        evaluation["details"].append(
            f"✓ Identified {len(found_states)}/13 states (+20)")
    elif len(found_states) >= 5:
        evaluation["score"] += 10
        evaluation["details"].append(
            f"~ Identified {len(found_states)}/13 states (+10)")
    elif len(found_states) > 0:
        evaluation["score"] += 5
        evaluation["details"].append(
            f"~ Identified {len(found_states)}/13 states (+5)")

    # Check for data points with values (30 points)
    data_points = data.get("data_points", [])
    has_numeric_values = False
    reasonable_values = 0

    for dp in data_points:
        # Check for numeric values
        for key in ["value", "value_2025", "value_2070"]:
            val = dp.get(key)
            if isinstance(val, (int, float)):
                has_numeric_values = True
                # Check if value is in reasonable range (0-150)
                if 0 < val <= 150:
                    reasonable_values += 1

    if has_numeric_values:
        if reasonable_values >= 10:
            evaluation["score"] += 30
            evaluation["details"].append(
                f"✓ Found {reasonable_values} reasonable numeric values (+30)")
        elif reasonable_values >= 5:
            evaluation["score"] += 20
            evaluation["details"].append(
                f"~ Found {reasonable_values} reasonable numeric values (+20)")
        else:
            evaluation["score"] += 10
            evaluation["details"].append(
                f"~ Found some numeric values but limited accuracy (+10)")
    else:
        evaluation["details"].append("✗ No numeric values extracted (0)")

    # Check for 2025 vs 2070 distinction (20 points)
    has_year_distinction = False
    for dp in data_points:
        if "2025" in str(dp) or "2070" in str(dp):
            has_year_distinction = True
            break

    if has_year_distinction:
        evaluation["score"] += 20
        evaluation["details"].append(
            "✓ Distinguished between 2025 and 2070 data (+20)")
    else:
        evaluation["details"].append("✗ Did not distinguish between years (0)")

    return evaluation


def main():
    # Find the test image
    image_path = os.path.join(settings.extraction_images_dir,
                              "page_1_figure_1.png")

    if not os.path.exists(image_path):
        print(f"Error: Image not found at {image_path}")
        print("Please run extraction first to generate the image.")
        return

    print("=" * 60)
    print("VISION MODEL COMPARISON TEST")
    print("=" * 60)
    print(f"\nTest image: {image_path}")
    print(f"\nGround Truth Reference:\n{GROUND_TRUTH[:500]}...")

    # Check available models
    available_base, available_full = get_available_models()
    print(f"\nAvailable models: {available_full}")

    # Load image
    image_base64 = load_image_as_base64(image_path)
    print(f"Image loaded ({len(image_base64)} bytes base64)")

    # Test each model
    results = []

    for model in VISION_MODELS:
        # Check if model is available
        model_base = model.split(':')[0]
        if model_base not in available_base and model not in available_full:
            print(f"\n⚠ Model '{model}' not available - skipping")
            print(f"  Install with: ollama pull {model}")
            continue

        result = test_model(model, image_base64)
        evaluation = evaluate_result(result)
        result["evaluation"] = evaluation
        results.append(result)

        # Print summary for this model
        print(
            f"\nEvaluation Score: {evaluation['score']}/{evaluation['max_score']}"
        )
        for detail in evaluation['details']:
            print(f"  {detail}")

        if result.get("parsed_json"):
            print(f"\nExtracted data preview:")
            preview = json.dumps(result["parsed_json"], indent=2)[:800]
            print(preview)

    # Final comparison
    print("\n" + "=" * 60)
    print("FINAL COMPARISON")
    print("=" * 60)

    if not results:
        print("\nNo models were tested. Please install at least one model:")
        for model in VISION_MODELS:
            print(f"  ollama pull {model}")
        return

    # Sort by score
    results.sort(key=lambda x: x.get("evaluation", {}).get("score", 0),
                 reverse=True)

    print(f"\n{'Model':<20} {'Score':<10} {'Time':<10} {'Status'}")
    print("-" * 50)

    for r in results:
        score = r.get("evaluation", {}).get("score", 0)
        time_s = r.get("time_seconds", 0)
        status = "✓" if r.get("success") else "✗"
        print(f"{r['model']:<20} {score:<10} {time_s:<10}s {status}")

    # Recommendation
    best = results[0]
    print(f"\n🏆 RECOMMENDED MODEL: {best['model']}")
    print(f"   Score: {best['evaluation']['score']}/100")
    print(f"   Time: {best['time_seconds']}s")

    # Save results
    output_path = os.path.join(os.getcwd(), "output",
                               "model_comparison_results.json")
    with open(output_path, 'w') as f:
        # Remove base64 from results to keep file small
        clean_results = []
        for r in results:
            clean_r = {k: v for k, v in r.items()}
            clean_results.append(clean_r)

        json.dump(
            {
                "timestamp": datetime.now().isoformat(),
                "image_path": image_path,
                "results": clean_results,
                "recommendation": best['model']
            },
            f,
            indent=2)

    print(f"\nResults saved to: {output_path}")


if __name__ == "__main__":
    main()
