import json
import logging
import os
import base64
from typing import Dict, Any, List, Optional, Union
import ollama
from config import settings

logger = logging.getLogger(__name__)


class Summarizer:
    """
    Enhanced summarizer that processes documents page-by-page.
    It re-analyzes images using a vision model, incorporating the current topic context
    to extract deeper, more relevant insights.
    """

    def __init__(self,
                 text_model: str = "llama3.2",
                 vision_model: str = "minicpm-v"):
        self.text_model = text_model
        self.vision_model = vision_model
        logger.info(
            f"Initialized Summarizer with text_model: {self.text_model}, vision_model: {self.vision_model}"
        )

    def summarize(self, extraction_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main entry point for document summarization.
        """
        logger.info(
            "Starting enhanced document summarization with image re-processing..."
        )

        # Check for sections first (Topic-wise summarization)
        sections = extraction_result.get("sections", [])
        if sections:
            logger.info(
                f"Found {len(sections)} sections. Summarizing by topic...")
            return self._summarize_by_sections(sections)

        # Fallback to page-by-page if no sections
        logger.info(
            "No sections found. Falling back to page-by-page summarization...")
        pages = extraction_result.get("pages", [])
        if not pages:
            logger.warning("No pages found in extraction result.")
            return {"global_summary": "", "page_summaries": []}

        page_summaries = []
        running_context = ""
        active_topics = []

        for i, page in enumerate(pages):
            page_num = page.get("page_number", i + 1)
            logger.info(f"Processing page {page_num}...")

            # 1. First, identify the context/topics from the text part of the page ONLY
            #    (This helps us ask better questions to the vision model)
            text_content = self._extract_text_only(page)
            preliminary_topics = self._identify_page_topics(
                text_content, running_context)

            # Combine global active topics with local preliminary topics
            current_context_topics = list(
                set(active_topics + preliminary_topics))

            # 2. Re-process images on this page using the context
            visual_insights_data = self._reanalyze_visuals(
                page, current_context_topics)

            # Format visual insights for the prompt
            visual_insights_str = "\n\n".join([
                f"[VISUAL RE-ANALYSIS ({v['type']})]: {v['analysis']}"
                for v in visual_insights_data
            ])

            # 3. Build full page content (Text + New Visual Insights)
            full_page_content = f"{text_content}\n\n{visual_insights_str}"

            # 4. Generate final summary for the page
            page_output = self._summarize_content(
                title=f"Page {page_num}",
                content=full_page_content,
                previous_context=running_context,
                active_topics=current_context_topics)

            # 5. Update running context
            current_summary = page_output.get("summary", "")
            running_context = self._update_running_context(
                running_context, current_summary)

            # Update active topics
            new_topics = page_output.get("topics", [])
            for topic in new_topics:
                if topic not in active_topics:
                    active_topics.append(topic)

            page_summaries.append({
                "page_number":
                page_num,
                "summary":
                current_summary,
                "topics":
                new_topics,
                "key_visuals":
                page_output.get("visual_insights", []),
                "detailed_visual_analysis":
                visual_insights_data
            })

        # Generate Global Summary
        logger.info("Generating global document summary...")
        global_summary = self._generate_global_summary(page_summaries)

        return {
            "global_summary": global_summary,
            "page_summaries": page_summaries,
            "all_topics": active_topics
        }

    def _summarize_by_sections(
            self, sections: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Summarize the document section by section (Topic-wise)."""
        topic_summaries = []
        running_context = ""
        all_topics = []

        for section in sections:
            title = section.get("title", "Untitled Section")
            logger.info(f"Processing section: {title}")

            # 1. Extract content and visuals (recursive)
            text_content, visual_elements = self._extract_section_data(section)

            if not text_content.strip() and not visual_elements:
                continue

            # 2. Identify topics
            preliminary_topics = self._identify_page_topics(
                text_content, running_context)
            current_topics = list(set(all_topics + preliminary_topics))

            # 3. Re-analyze visuals
            visual_insights_data = self._reanalyze_visuals_list(
                visual_elements, current_topics)

            visual_insights_str = "\n\n".join([
                f"[VISUAL RE-ANALYSIS ({v['type']})]: {v['analysis']}"
                for v in visual_insights_data
            ])

            # 4. Build full content
            full_content = f"{text_content}\n\n{visual_insights_str}"

            # 5. Summarize
            section_output = self._summarize_content(
                title=title,
                content=full_content,
                previous_context=running_context,
                active_topics=current_topics)

            summary_text = section_output.get("summary", "")
            running_context = self._update_running_context(
                running_context, summary_text)

            new_topics = section_output.get("topics", [])
            for t in new_topics:
                if t not in all_topics:
                    all_topics.append(t)

            topic_summaries.append({
                "topic":
                title,
                "original_content":
                text_content,
                "summary":
                summary_text,
                "key_insights":
                section_output.get("visual_insights", []),
                "visual_analysis":
                visual_insights_data,
                "topics":
                new_topics
            })

        global_summary = self._generate_global_summary_from_topics(
            topic_summaries)

        return {
            "global_summary": global_summary,
            "topic_summaries": topic_summaries,
            "all_topics": all_topics
        }

    def _extract_section_data(
            self, section: Dict[str, Any]) -> tuple[str, List[Dict[str, Any]]]:
        """Recursively extract text and visuals from a section."""
        text_parts = []
        visuals = []

        # Title
        if section.get("title"):
            text_parts.append(f"## {section['title']}")

        # Paragraphs
        for p in section.get("paragraphs", []):
            if isinstance(p, dict):
                text_parts.append(p.get("content", ""))
            elif isinstance(p, str):
                text_parts.append(p)

        # Bullet points
        for bp in section.get("bullet_points", []):
            if isinstance(bp, list):
                for item in bp:
                    text_parts.append(f"- {item}")
            elif isinstance(bp, dict):
                if "bullet_items" in bp and bp["bullet_items"]:
                    for item in bp["bullet_items"]:
                        text_parts.append(f"- {item}")
                else:
                    text_parts.append(f"- {bp.get('content', '')}")
            elif isinstance(bp, str):
                text_parts.append(f"- {bp}")

        # Numbered lists
        for nl in section.get("numbered_lists", []):
            text_parts.append(f"1. {nl.get('content', '')}")

        # Visuals
        visuals.extend(section.get("figures", []))
        visuals.extend(section.get("tables", []))

        # Subsections (Recursive)
        for sub in section.get("subsections", []):
            sub_text, sub_visuals = self._extract_section_data(sub)
            text_parts.append(sub_text)
            visuals.extend(sub_visuals)

        return "\n\n".join(text_parts), visuals

    def _reanalyze_visuals_list(
            self, elements: List[Dict[str, Any]],
            context_topics: List[str]) -> List[Dict[str, Any]]:
        """Re-analyze a list of visual elements."""
        visual_analysis_results = []
        topics_str = ", ".join(
            context_topics) if context_topics else "General Analysis"

        for elem in elements:
            etype = elem.get("type", "")
            image_context = elem.get("image_context", {})
            image_path = image_context.get("image_path")

            # Check if we have the image file
            full_path = os.path.join(settings.output_dir,
                                     image_path) if image_path else ""

            # Handle relative path if needed
            if image_path and not os.path.exists(full_path):
                possible_path = os.path.join(settings.extraction_images_dir,
                                             os.path.basename(image_path))
                if os.path.exists(possible_path):
                    full_path = possible_path

            analysis_entry = {
                "type": etype,
                "image_path": image_path,
                "context_topics": context_topics,
                "analysis": "",
                "source": "vision_model"
            }

            if full_path and os.path.exists(full_path):
                logger.info(
                    f"Re-analyzing image: {full_path} with context: {topics_str}"
                )
                try:
                    with open(full_path, "rb") as img_file:
                        img_base64 = base64.b64encode(
                            img_file.read()).decode('utf-8')

                    # Special handling for Page 1 Figure 1
                    special_instructions = ""
                    if "page_1_figure_1" in str(image_path):
                        special_instructions = """
                        SPECIAL CONTEXT FOR THIS IMAGE:
                        - This image contains 1 illustration (map) on the left and 2 graphs on the right.
                        - Left illustration: Map showing "Recipient states West" (Pink), "Recipient states East" (Light Pink), and "Donor states West" (Blue).
                        - Right graphs: Two bar charts for years 2025 and 2070.
                        - Y-axis: Starts from 0 and ends at 150.
                        - X-axis: Abbreviations of state names.
                        - Color coding in graphs matches the map:
                            - Blue: Donor states West
                            - Pink: Recipient states West
                            - Light Pink: Recipient states East
                        
                        Please extract the specific values for the states in 2025 vs 2070 based on this structure.
                        """

                    prompt = f"""
                    Analyze this image in the context of: {topics_str}.
                    
                    Current Text Context (for reference):
                    {elem.get('content', '')}
                    {special_instructions}
                    
                    INSTRUCTIONS:
                    1. Describe what this visual shows specifically related to the topics above.
                    2. Extract any specific data points or trends that support or contradict the text.
                    3. If it's a chart, read the key values.
                    
                    Provide a concise but insightful analysis.
                    """

                    analysis = self._call_ollama_vision(prompt, img_base64)
                    analysis_entry["analysis"] = analysis
                    visual_analysis_results.append(analysis_entry)

                except Exception as e:
                    logger.error(f"Failed to process image {full_path}: {e}")
                    desc = image_context.get("description", "")
                    analysis_entry["analysis"] = desc
                    analysis_entry["source"] = "fallback_metadata"
                    visual_analysis_results.append(analysis_entry)
            else:
                desc = image_context.get("description", "")
                analysis_entry["analysis"] = desc
                analysis_entry["source"] = "existing_metadata"
                visual_analysis_results.append(analysis_entry)

        return visual_analysis_results

    def _summarize_content(self, title: str, content: str,
                           previous_context: str,
                           active_topics: List[str]) -> Dict[str, Any]:
        """
        Summarizes content (page or section) using Ollama.
        """
        prompt = f"""
        You are an expert analyst summarizing a document section: "{title}".
        
        CURRENT STATUS:
        - Section/Page: {title}
        - Previous Context: {previous_context if previous_context else "Start of document"}
        - Active Topics: {', '.join(active_topics) if active_topics else "None"}

        CONTENT (Text + Visual Analysis):
        {content} 

        INSTRUCTIONS:
        1. Synthesize the text content and the visual analysis into a cohesive summary.
        2. Highlight how the visuals support the text arguments.
        3. Identify any new topics introduced.
        
        OUTPUT FORMAT (JSON ONLY):
        {{
            "summary": "Detailed narrative summary...",
            "visual_insights": ["Key insight 1", "Key insight 2"],
            "topics": ["Topic A", "Topic B"]
        }}
        """

        response = self._call_ollama(prompt, json_mode=True)
        try:
            return json.loads(response)
        except:
            return {"summary": response, "visual_insights": [], "topics": []}

    def _generate_global_summary_from_topics(
            self, topic_summaries: List[Dict[str, Any]]) -> str:
        combined_text = ""
        for t in topic_summaries:
            combined_text += f"\n\nTopic: {t['topic']}\nSummary:\n{t['summary']}"
            if t['key_insights']:
                combined_text += "\nKey Visual Insights:\n" + "\n".join(
                    f"- {v}" for v in t['key_insights'])

        prompt = f"""
        Create a comprehensive Global Summary of the entire document based on these topic summaries.

        DOCUMENT CONTENT SUMMARIES:
        {combined_text}

        INSTRUCTIONS:
        1. Write an Executive Summary.
        2. List Main Themes.
        3. Summarize key data from charts.
        
        Return in Markdown.
        """
        return self._call_ollama(prompt, json_mode=False)

    def _extract_text_only(self, page: Dict[str, Any]) -> str:
        """Extracts only the text elements from the page."""
        elements = page.get("elements", [])
        text_parts = []

        # Add Page Title
        title = page.get("title")
        if title:
            text_parts.append(f"# Page Title: {title}")

        for elem in elements:
            etype = elem.get("type", "unknown")
            text = elem.get("content", "")

            # Skip visuals here, we only want text to build context
            if etype in ["figure", "chart", "table", "image"]:
                continue

            if etype in ["title", "section_title"]:
                text_parts.append(f"## {text}")
            elif etype in ["paragraph", "text", "footnote"]:
                text_parts.append(text)
            elif etype in ["bullet_point", "list_item"]:
                if "bullet_items" in elem:
                    for item in elem["bullet_items"]:
                        text_parts.append(f"- {item}")
                else:
                    text_parts.append(f"- {text}")

        return "\n\n".join(text_parts)

    def _identify_page_topics(self, text_content: str,
                              previous_context: str) -> List[str]:
        """Quickly identify main topics on the page to inform visual analysis."""
        if not text_content.strip():
            return []

        prompt = f"""
        Identify the top 3 main topics discussed in this text.
        
        Previous Context: {previous_context}
        
        Current Text:
        {text_content}
        
        Return ONLY a JSON list of strings, e.g. ["Fiscal Policy", "Demographics"].
        """
        response = self._call_ollama(prompt, json_mode=True)
        try:
            result = json.loads(response)
            if isinstance(result, list):
                return result
            elif isinstance(result, dict):
                # Handle case where LLM returns {"topics": [...]}
                for key, value in result.items():
                    if isinstance(value, list):
                        return value
            return []
        except:
            return []

    def _reanalyze_visuals(self, page: Dict[str, Any],
                           context_topics: List[str]) -> List[Dict[str, Any]]:
        """
        Finds images in the page, loads them, and re-analyzes them using the Vision Model.
        Returns a list of structured analysis results.
        """
        elements = page.get("elements", [])
        visual_analysis_results = []

        topics_str = ", ".join(
            context_topics) if context_topics else "General Analysis"

        for elem in elements:
            etype = elem.get("type", "")
            if etype in ["figure", "chart", "table", "image"]:
                image_context = elem.get("image_context", {})
                image_path = image_context.get("image_path")

                # Check if we have the image file
                full_path = os.path.join(settings.output_dir,
                                         image_path) if image_path else ""

                # Handle relative path if needed (extraction output might have 'images/...')
                if image_path and not os.path.exists(full_path):
                    # Try relative to project root or extraction dir
                    possible_path = os.path.join(
                        settings.extraction_images_dir,
                        os.path.basename(image_path))
                    if os.path.exists(possible_path):
                        full_path = possible_path

                analysis_entry = {
                    "type": etype,
                    "image_path": image_path,
                    "context_topics": context_topics,
                    "analysis": "",
                    "source": "vision_model"
                }

                if full_path and os.path.exists(full_path):
                    logger.info(
                        f"Re-analyzing image: {full_path} with context: {topics_str}"
                    )

                    # Read image as base64
                    try:
                        with open(full_path, "rb") as img_file:
                            img_base64 = base64.b64encode(
                                img_file.read()).decode('utf-8')

                        # Special handling for Page 1 Figure 1
                        special_instructions = ""
                        if "page_1_figure_1" in str(image_path):
                            special_instructions = """
                            SPECIAL CONTEXT FOR THIS IMAGE:
                            - This image contains 1 illustration (map) on the left and 2 graphs on the right.
                            - Left illustration: Map showing "Recipient states West" (Pink), "Recipient states East" (Light Pink), and "Donor states West" (Blue).
                            - Right graphs: Two bar charts for years 2025 and 2070.
                            - Y-axis: Starts from 0 and ends at 150.
                            - X-axis: Abbreviations of state names.
                            - Color coding in graphs matches the map:
                                - Blue: Donor states West
                                - Pink: Recipient states West
                                - Light Pink: Recipient states East
                            
                            Please extract the specific values for the states in 2025 vs 2070 based on this structure.
                            """

                        prompt = f"""
                        Analyze this image in the context of: {topics_str}.
                        
                        Current Page Text Context (for reference):
                        {elem.get('content', '')}
                        {special_instructions}
                        
                        INSTRUCTIONS:
                        1. Describe what this visual shows specifically related to the topics above.
                        2. Extract any specific data points or trends that support or contradict the text.
                        3. If it's a chart, read the key values.
                        
                        Provide a concise but insightful analysis.
                        """

                        analysis = self._call_ollama_vision(prompt, img_base64)
                        analysis_entry["analysis"] = analysis
                        visual_analysis_results.append(analysis_entry)

                    except Exception as e:
                        logger.error(
                            f"Failed to process image {full_path}: {e}")
                        # Fallback to existing description
                        desc = image_context.get("description", "")
                        analysis_entry["analysis"] = desc
                        analysis_entry["source"] = "fallback_metadata"
                        visual_analysis_results.append(analysis_entry)
                else:
                    # No image file found, fallback to existing metadata
                    desc = image_context.get("description", "")
                    analysis_entry["analysis"] = desc
                    analysis_entry["source"] = "existing_metadata"
                    visual_analysis_results.append(analysis_entry)

        return visual_analysis_results

    def _summarize_page(self, page_num: int, content: str,
                        previous_context: str,
                        active_topics: List[str]) -> Dict[str, Any]:
        """
        Summarizes a single page using Ollama, considering cross-page context.
        """
        return self._summarize_content(f"Page {page_num}", content,
                                       previous_context, active_topics)

    def _update_running_context(self, current_context: str,
                                new_summary: str) -> str:
        return current_context + "\n\n" + new_summary

    def _generate_global_summary(self, page_summaries: List[Dict[str,
                                                                 Any]]) -> str:
        combined_text = ""
        for p in page_summaries:
            combined_text += f"\n\nPage {p['page_number']} Summary:\n{p['summary']}"
            if p['key_visuals']:
                combined_text += "\nKey Visuals:\n" + "\n".join(
                    f"- {v}" for v in p['key_visuals'])

        prompt = f"""
        Create a comprehensive Global Summary of the entire document based on these page summaries.

        DOCUMENT CONTENT SUMMARIES:
        {combined_text}

        INSTRUCTIONS:
        1. Write an Executive Summary.
        2. List Main Themes.
        3. Summarize key data from charts.
        
        Return in Markdown.
        """
        return self._call_ollama(prompt, json_mode=False)

    def save_output(self,
                    summary_data: Dict[str, Any],
                    output_dir: Optional[str] = None,
                    filename: str = "summary_result.json"):
        if output_dir is None:
            output_dir = settings.summarization_output_dir
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, filename)
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(summary_data, f, indent=2, ensure_ascii=False)
            logger.info(f"Summary saved to {output_path}")
            return output_path
        except Exception as e:
            logger.error(f"Failed to save summary: {e}")
            return None

    def _call_ollama(self, prompt: str, json_mode: bool = False) -> str:
        try:
            options = {"temperature": 0.3, "num_ctx": 32768}
            response = ollama.generate(model=self.text_model,
                                       prompt=prompt,
                                       format='json' if json_mode else '',
                                       options=options,
                                       stream=False)
            return response.get("response", "").strip()
        except Exception as e:
            logger.error(f"Ollama generation failed: {e}")
            return "{}" if json_mode else f"Error: {e}"

    def _call_ollama_vision(self, prompt: str, image_base64: str) -> str:
        try:
            response = ollama.generate(model=self.vision_model,
                                       prompt=prompt,
                                       images=[image_base64],
                                       stream=False)
            return response.get("response", "").strip()
        except Exception as e:
            logger.error(f"Ollama vision generation failed: {e}")
            return "Error analyzing image."


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        with open(settings.extraction_output_path, 'r') as f:
            data = json.load(f)

        # Ensure we have the vision model pulled (optional check)
        summarizer = Summarizer(vision_model="minicpm-v")  # or llava
        result = summarizer.summarize(data)
        summarizer.save_output(result)

    except FileNotFoundError:
        print("Extraction result file not found.")
