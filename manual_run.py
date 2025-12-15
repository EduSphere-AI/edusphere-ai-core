import os
import json
import logging
from config import settings
from features.extraction import Extraction
from features.summarization import Summarizer
from features.generation import SlideGenerator
from utils.logging_config import setup_logging

setup_logging()
logger = logging.getLogger(__name__)


def main():
    logger.info("Starting manual pipeline run...")

    # 1. Extraction
    input_pdf = settings.input_file_path
    extraction_output = settings.extraction_output_path
    images_dir = settings.extraction_images_dir

    logger.info(f"Input PDF: {input_pdf}")
    logger.info(f"Extraction Output: {extraction_output}")
    logger.info(f"Images Dir: {images_dir}")

    if not os.path.exists(input_pdf):
        logger.error(f"Input file not found: {input_pdf}")
        return

    # Create directories
    os.makedirs(os.path.dirname(extraction_output), exist_ok=True)
    os.makedirs(images_dir, exist_ok=True)

    logger.info("--- Step 1: Extraction ---")
    extractor = Extraction(
        inp_file_path=input_pdf,
        output_file_path=extraction_output,
        output_image_dir=images_dir,
        use_ollama=True,
        extract_images=True,
    )
    extractor.extract()
    logger.info("Extraction completed.")

    # 2. Summarization
    logger.info("--- Step 2: Summarization ---")

    # Read extraction result
    with open(extraction_output, 'r') as f:
        extraction_data = json.load(f)

    summarizer = Summarizer()
    summary_result = summarizer.summarize(extraction_data)

    # Save summary result
    summary_dir = settings.summarization_output_dir
    os.makedirs(summary_dir, exist_ok=True)
    summary_output_path = os.path.join(summary_dir, "summary_result.json")

    with open(summary_output_path, 'w') as f:
        json.dump(summary_result, f, indent=2, ensure_ascii=False)

    logger.info(f"Summarization completed. Saved to {summary_output_path}")

    # 3. Generation
    logger.info("--- Step 3: Generation ---")

    generation_output = settings.generation_output_path
    os.makedirs(os.path.dirname(generation_output), exist_ok=True)

    generator = SlideGenerator()
    # Use summarization output as input for generation
    # This enables using the detailed summaries instead of raw extraction
    generator.generate(input_file=summary_output_path,
                       output_file=generation_output)

    logger.info(f"Generation completed. Saved to {generation_output}")


if __name__ == "__main__":
    main()
