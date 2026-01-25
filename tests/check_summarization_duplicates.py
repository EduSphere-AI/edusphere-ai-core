import json
import os
from collections import defaultdict


def check_summarization_duplicates():
    base_dir = os.path.join(os.path.dirname(__file__), "..")
    file_path = os.path.join(base_dir, "output", "summarization",
                             "summary_result.json")

    if not os.path.exists(file_path):
        print(f"Error: File not found at {file_path}")
        return

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error reading JSON: {e}")
        return

    topic_summaries = data.get("topic_summaries", [])
    print(f"Total topic summaries: {len(topic_summaries)}")

    # 1. Check for Duplicate Topics
    topic_counts = defaultdict(int)
    for item in topic_summaries:
        topic = item.get("topic", "").strip()
        if topic:
            topic_counts[topic] += 1

    duplicate_topics = {k: v for k, v in topic_counts.items() if v > 1}

    if duplicate_topics:
        print(f"\n[!] Found {len(duplicate_topics)} duplicate topics:")
        for topic, count in duplicate_topics.items():
            print(f"  - '{topic}': {count} occurrences")
    else:
        print("\n[+] No duplicate topics found.")

    # 2. Check for Duplicate Summaries (> 20 chars)
    summary_counts = defaultdict(list)
    for item in topic_summaries:
        summary = item.get("summary", "").strip()
        topic = item.get("topic", "unknown")
        if len(summary) > 20:
            summary_counts[summary].append(topic)

    duplicate_summaries = {
        k: v
        for k, v in summary_counts.items() if len(v) > 1
    }

    if duplicate_summaries:
        print(
            f"\n[!] Found {len(duplicate_summaries)} duplicate summaries (>20 chars):"
        )
        for summary, topics in duplicate_summaries.items():
            preview = summary[:60].replace('\n', ' ') + "..."
            print(
                f"  - '{preview}': {len(topics)} occurrences (Topics: {topics})"
            )
    else:
        print("\n[+] No duplicate summaries found.")


if __name__ == "__main__":
    check_summarization_duplicates()
