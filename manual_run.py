import os
import sys
os.environ['PYTHONIOENCODING'] = 'utf-8'

if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import json
import logging
from config import settings
from features.extraction import Extraction
from features.summarization import Summarizer
from features.generation import SlideGenerator
from utils.logging_config import setup_logging
from utils.ollama_translator import OllamaTranslator  # ✅ NEW

setup_logging()
logger = logging.getLogger(__name__)


def main(target_language: str = 'en'):
    """
    Main pipeline with Ollama translation support
    
    Args:
        target_language: Language code (e.g., 'hi', 'ta', 'es')
    """
    logger.info("Starting manual pipeline run...")
    
    # Initialize Ollama translator
    translator = OllamaTranslator(model='mistral')
    
    logger.info(f"Target language: {target_language}")

    # 1. Extraction
    input_pdf = settings.input_file_path
    extraction_output = settings.extraction_output_path
    images_dir = settings.extraction_images_dir

    if not os.path.exists(input_pdf):
        logger.error(f"Input file not found: {input_pdf}")
        return

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

    try:
        with open(extraction_output, 'r', encoding='utf-8') as f:
            extraction_data = json.load(f)
    except UnicodeDecodeError:
        with open(extraction_output, 'r', encoding='utf-8', errors='replace') as f:
            extraction_data = json.load(f)

    summarizer = Summarizer()
    summary_result = summarizer.summarize(extraction_data)

    summary_dir = settings.summarization_output_dir
    os.makedirs(summary_dir, exist_ok=True)
    summary_output_path = os.path.join(summary_dir, "summary_result.json")

    with open(summary_output_path, 'w', encoding='utf-8') as f:
        json.dump(summary_result, f, indent=2, ensure_ascii=False)

    logger.info(f"Summarization completed.")

    # 3. Generation
    logger.info("--- Step 3: Generation ---")

    generation_output = settings.generation_output_path
    os.makedirs(os.path.dirname(generation_output), exist_ok=True)

    generator = SlideGenerator()
    generator.generate(input_file=summary_output_path, output_file=generation_output)

    logger.info(f"Generation completed.")

    # ✅ NEW: Step 4. Translation with Ollama (if not English)
    if target_language != 'en':
        logger.info("--- Step 4: Translation with Ollama ---")
        
        try:
            with open(generation_output, 'r', encoding='utf-8') as f:
                generation_data = json.load(f)
            
            # Translate slides
            if 'slides' in generation_data:
                logger.info(f"Translating slides to {target_language}...")
                generation_data['slides'] = translator.translate_slides(
                    generation_data['slides'], 
                    target_language
                )
            
            # Translate chapters
            if 'chapters' in generation_data:
                logger.info(f"Translating chapters to {target_language}...")
                generation_data['chapters'] = translator.translate_list(
                    generation_data['chapters'],
                    target_language
                )
            
            # Save translated output
            translated_output_path = generation_output.replace(
                '.json', 
                f'_{target_language}.json'
            )
            with open(translated_output_path, 'w', encoding='utf-8') as f:
                json.dump(generation_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Translation completed. Saved to {translated_output_path}")
            
        except Exception as e:
            logger.error(f"Translation failed: {e}")


if __name__ == "__main__":
    # Usage examples:
    # main()              # English (no translation)
    # main('hi')          # Hindi
    # main('ta')          # Tamil
    # main('es')          # Spanish
    # main('fr')          # French
    
    main('hi')  # Change to desired language