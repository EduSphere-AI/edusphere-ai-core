import os
import logging
from typing import List, Dict, Any, Optional, Tuple
import json
import re
import base64
from io import BytesIO
import unicodedata

import pdfplumber
import ollama
from PIL import Image

logger = logging.getLogger(__name__)


class Extractor:
    """
    Advanced PDF Extractor using pdfplumber for layout analysis and Ollama for semantic understanding.
    """
    file_path: str
    output_file_path: str
    vision_model: str = "llava"
    text_model: str = "llama3.2"  # or mistral, llama3, etc.

    def __init__(self,
                 inp_file_path: str | None = None,
                 output_file_path: str | None = None):
        """
        :param inp_file_path: Path to the PDF file
        :type inp_file_path: str | None
        :param output_file_path: Path to the output JSON file
        :type output_file_path: str | None
        """
        # Default paths
        cwd = os.getcwd()
        if "features" in cwd:
            cwd = cwd.replace("/features", "")

        default_input = os.path.join(cwd, "data", "input.pdf")
        self.file_path = inp_file_path if inp_file_path else default_input

        # Path resolution logic from original code
        if inp_file_path and not os.path.isabs(inp_file_path):
            self.file_path = os.path.join(cwd, inp_file_path)

        if not os.path.exists(self.file_path):
            # Fallback check
            if os.path.exists(
                    os.path.join(cwd, "data",
                                 os.path.basename(self.file_path))):
                self.file_path = os.path.join(cwd, "data",
                                              os.path.basename(self.file_path))
            else:
                logger.error(f"File not found: {self.file_path}")
                raise FileNotFoundError(f"File not found: {self.file_path}")

        self.output_file_path = output_file_path if output_file_path else os.path.join(
            cwd, "output", "extraction_result.json")

        # Ensure output directory exists
        os.makedirs(os.path.dirname(self.output_file_path), exist_ok=True)

        # Ensure images directory exists
        self.images_dir = os.path.join(os.path.dirname(self.output_file_path),
                                       "images")
        os.makedirs(self.images_dir, exist_ok=True)

        logger.info(f"Initialized Extractor for: {self.file_path}")

    def clean_text(self, text: str) -> str:
        """
        Cleans text by normalizing unicode, removing non-printable chars, and collapsing whitespace.
        """
        if not text:
            return ""
        # Normalize unicode characters
        text = unicodedata.normalize('NFKD', text)
        # Remove non-printable characters (keep newlines/tabs)
        text = ''.join(c for c in text if c.isprintable() or c in ['\n', '\t'])

        # Fix hyphenation (e.g. "exam-\nple" -> "example")
        text = re.sub(r'(\w+)-\n(\w+)', r'\1\2', text)

        # Replace newlines with spaces
        text = text.replace('\n', ' ')

        # Replace multiple spaces with single space
        text = re.sub(r'\s+', ' ', text)

        return text.strip()

    def _call_ollama(self,
                     model: str,
                     prompt: str,
                     images: List[str] | None = None) -> str:
        """
        Helper to call Ollama API using the official library.
        """
        try:
            logger.debug(
                f"Calling Ollama model: {model} with prompt length: {len(prompt)}"
            )
            response = ollama.generate(model=model,
                                       prompt=prompt,
                                       images=images,
                                       stream=False)
            logger.debug("Ollama call successful")
            return response.get("response", "")
        except Exception as e:
            logger.warning(f"Ollama call failed: {e}. Is Ollama running?")
            return f"[Error calling Ollama: {e}]"

    def analyze_image(self, image: Image.Image,
                      image_filename: str) -> Dict[str, Any]:
        """
        Uses a VLM to analyze an image (chart, graph, or photo).
        Saves the image to disk and returns structured analysis.
        """
        logger.debug(f"Starting image analysis for {image_filename}...")

        # Save image to disk
        image_path = os.path.join(self.images_dir, image_filename)
        image.save(image_path)

        buffered = BytesIO()
        image.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")

        prompt = (
            "Analyze this image. Provide the output in valid JSON format. "
            "If it is a chart or graph, extract the data points, axes, and trends. "
            "Structure the JSON as follows:\n"
            "{\n"
            '  "type": "chart" | "graph" | "image" | "diagram",\n'
            '  "title": "...",\n'
            '  "description": "...",\n'
            '  "data": { "x_axis": "...", "y_axis": "...", "points": [...] },\n'  # Optional, for charts
            '  "text_content": "..."\n'
            "}\n"
            "Return ONLY the JSON object.")

        response_text = self._call_ollama(self.vision_model,
                                          prompt,
                                          images=[img_str])

        # Attempt to parse JSON
        try:
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                analysis = json.loads(json_match.group(0))
            else:
                analysis = {"type": "unknown", "description": response_text}
        except Exception as e:
            logger.warning(f"Failed to parse JSON from image analysis: {e}")
            analysis = {"type": "unknown", "description": response_text}

        logger.debug("Image analysis complete.")
        return {"image_path": f"images/{image_filename}", "analysis": analysis}

    def refine_text_structure(self,
                              text_block: str,
                              context: str = "") -> Dict[str, Any]:
        """
        Uses an LLM to structure raw text into meaningful JSON.
        """
        logger.debug(
            f"Refining text structure for block of length {len(text_block)}")
        prompt = (
            f"Analyze the following text extracted from a PDF page. "
            f"Context: {context}\n\n"
            f"Text:\n{text_block}\n\n"
            f"Task: Identify the role of this text (Title, Subtitle, Heading, Paragraph, Footer, Caption). "
            f"Clean any remaining artifacts. "
            f"Return ONLY a JSON object with keys: 'role', 'cleaned_text', 'summary'."
        )

        response = self._call_ollama(self.text_model, prompt)
        try:
            # Try to parse JSON from response (Ollama might add chat text)
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(0))
            return {
                "role": "unknown",
                "cleaned_text": text_block,
                "summary": response
            }
        except:
            logger.warning(
                "Failed to parse JSON from Ollama response in refine_text_structure"
            )
            return {
                "role": "unknown",
                "cleaned_text": text_block,
                "summary": response
            }

    def summarize_page(self, text_content: str) -> str:
        """
        Summarizes the page content using Ollama.
        """
        logger.debug(f"Summarizing page content of length {len(text_content)}")
        prompt = f"Summarize the following content from a PDF page into a concise paragraph:\n\n{text_content[:4000]}"
        return self._call_ollama(self.text_model, prompt)

    def extract(self):
        """
        Main extraction method.
        """
        logger.info("Starting extraction process...")
        extracted_data = {"metadata": {}, "pages": []}

        try:
            with pdfplumber.open(self.file_path) as pdf:
                extracted_data["metadata"] = pdf.metadata

                for i, page in enumerate(pdf.pages):
                    logger.info(f"Processing page {i+1}...")
                    page_content = {"page_number": i + 1, "elements": []}

                    # 1. Extract Images
                    # pdfplumber image extraction can be tricky.
                    # We'll look for image objects and crop them.
                    for img_idx, img in enumerate(page.images):
                        # Get image bounding box
                        bbox = (img['x0'], img['top'], img['x1'],
                                img['bottom'])
                        try:
                            cropped_page = page.crop(bbox)
                            pil_image = cropped_page.to_image(
                                resolution=300).original

                            image_filename = f"page_{i+1}_img_{img_idx+1}.png"
                            logger.info(f"Analyzing image {image_filename}...")

                            analysis = self.analyze_image(
                                pil_image, image_filename)

                            page_content["elements"].append({
                                "type":
                                "image",
                                "bbox":
                                bbox,
                                "analysis":
                                analysis
                            })
                        except Exception as e:
                            logger.warning(
                                f"Failed to extract image on page {i+1}: {e}")

                    # 2. Extract Text with Layout Info
                    # We use extract_words to get position and font info
                    words = page.extract_words(
                        extra_attrs=['fontname', 'size'])

                    # ---------------------------------------------------------
                    # Step 1: Cluster words into "Line Segments"
                    # (Split lines if there is a large horizontal gap, e.g. columns)
                    # ---------------------------------------------------------
                    words.sort(key=lambda w: (w['top'], w['x0']))

                    segments = []
                    current_segment = []

                    for word in words:
                        if not current_segment:
                            current_segment.append(word)
                            continue

                        last_word = current_segment[-1]

                        # Check vertical alignment (same line)
                        # Tolerance of 3 points for "same line"
                        is_same_line = abs(word['top'] - last_word['top']) < 3

                        # Check horizontal proximity (same segment)
                        # Calculate dynamic threshold based on font size (approx 2 spaces)
                        char_width = last_word['x1'] - last_word['x0']
                        gap_threshold = max(10, last_word['size'] * 2)

                        dist_x = word['x0'] - last_word['x1']
                        is_close_x = dist_x < gap_threshold

                        if is_same_line and is_close_x:
                            current_segment.append(word)
                        else:
                            # Finalize current segment
                            segments.append(current_segment)
                            current_segment = [word]

                    if current_segment:
                        segments.append(current_segment)

                    # Convert list of words to Segment objects (dicts)
                    processed_segments = []
                    for seg in segments:
                        text = " ".join([w['text'] for w in seg])
                        top = min(w['top'] for w in seg)
                        bottom = max(w['bottom'] for w in seg)
                        x0 = min(w['x0'] for w in seg)
                        x1 = max(w['x1'] for w in seg)
                        avg_size = sum(w['size'] for w in seg) / len(seg)

                        processed_segments.append({
                            "text": text,
                            "top": top,
                            "bottom": bottom,
                            "x0": x0,
                            "x1": x1,
                            "size": avg_size
                        })

                    # ---------------------------------------------------------
                    # Step 2: Cluster Segments into "Text Blocks" (Paragraphs)
                    # (Merge segments that are vertically close and horizontally aligned)
                    # ---------------------------------------------------------
                    # Sort segments by top position to process in flow order
                    processed_segments.sort(key=lambda s: s['top'])

                    blocks = []

                    for seg in processed_segments:
                        merged = False
                        # Try to merge with an existing block
                        # We look at the most recently added blocks first (likely candidates)
                        for block in reversed(blocks):
                            last_seg = block[-1]

                            # 1. Vertical Check: Is it below the last segment?
                            # Allow some gap (e.g. 1.5 lines), but not too far (new section)
                            # Also check it's not *above* (shouldn't happen due to sort, but safety)
                            vertical_dist = seg['top'] - last_seg['bottom']

                            # Heuristic: Gap < 2 * font_size
                            is_vertical_close = 0 <= vertical_dist < (
                                seg['size'] * 2.5)

                            # 2. Horizontal Overlap Check: Do they align?
                            # Calculate overlap
                            overlap_start = max(seg['x0'], last_seg['x0'])
                            overlap_end = min(seg['x1'], last_seg['x1'])
                            overlap_width = overlap_end - overlap_start

                            # Require significant overlap relative to the narrower segment
                            min_width = min(seg['x1'] - seg['x0'],
                                            last_seg['x1'] - last_seg['x0'])
                            is_aligned = overlap_width > (min_width * 0.5)

                            # 3. Font Size Check
                            is_same_size = abs(seg['size'] -
                                               last_seg['size']) < 2

                            if is_vertical_close and is_aligned and is_same_size:
                                block.append(seg)
                                merged = True
                                break

                        if not merged:
                            blocks.append([seg])

                    # ---------------------------------------------------------
                    # Step 3: Sort Blocks for Reading Order
                    # (Sort by Column (x0) then Vertical (top))
                    # ---------------------------------------------------------
                    # We define a "Column" roughly.
                    # Simple sort by x0 then top works well for 2-column layouts.
                    # To avoid minor x-jitter causing reordering, we can round x0.

                    def sort_key(b):
                        first_seg = b[0]
                        # Round x0 to nearest 50px to group columns
                        col_bucket = round(first_seg['x0'] / 20) * 20
                        return (col_bucket, first_seg['top'])

                    blocks.sort(key=sort_key)

                    # ---------------------------------------------------------
                    # Step 4: Process Blocks into Final Elements
                    # ---------------------------------------------------------
                    # Calculate average font size for the page
                    all_sizes = [w['size'] for w in words]
                    page_avg_size = sum(all_sizes) / len(
                        all_sizes) if all_sizes else 10

                    for block in blocks:
                        # Join segments
                        block_text = "\n".join([s['text'] for s in block])

                        # Calculate block metrics
                        avg_block_size = sum([s['size']
                                              for s in block]) / len(block)

                        role = "paragraph"
                        if avg_block_size > page_avg_size * 1.5:
                            role = "title"
                        elif avg_block_size > page_avg_size * 1.2:
                            role = "heading"
                        elif avg_block_size < page_avg_size * 0.8:
                            role = "footer"

                        # Check for list items
                        if re.match(r'^[\u2022\-\*]|\d+\.',
                                    block_text.strip()):
                            role = "list_item"

                        clean_content = self.clean_text(block_text)
                        if clean_content:
                            page_content["elements"].append({
                                "type":
                                "text",
                                "role":
                                role,
                                "content":
                                clean_content,
                                "font_size":
                                round(avg_block_size, 2)
                            })

                    # 3. Page Context/Summary
                    full_page_text = " ".join([
                        el['content'] for el in page_content["elements"]
                        if el['type'] == 'text'
                    ])
                    if full_page_text:
                        logger.info(f"Summarizing page {i+1}...")
                        page_content["summary"] = self.summarize_page(
                            full_page_text)

                    extracted_data["pages"].append(page_content)

        except Exception as e:
            logger.error(f"Extraction failed: {e}")
            raise

        # Save to file
        with open(self.output_file_path, 'w', encoding='utf-8') as f:
            json.dump(extracted_data, f, indent=2, ensure_ascii=False)

        logger.info(f"Extraction complete. Saved to {self.output_file_path}")
        return extracted_data


if __name__ == "__main__":
    # Example usage
    # Ensure you have Ollama running: `ollama serve`
    # And pull models: `ollama pull llava`, `ollama pull llama3.2`

    # Configure logging for standalone execution
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    try:
        extractor = Extractor()  # Will use default path or find input.pdf
        result = extractor.extract()
        # print(json.dumps(result, indent=2))
    except Exception as e:
        logger.error(f"Error during execution: {e}")
