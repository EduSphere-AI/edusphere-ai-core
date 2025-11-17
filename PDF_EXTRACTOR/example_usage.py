"""
Example usage script for PDF Content Extractor.

This script demonstrates how to use the PDF extractor to extract
content from academic PDFs and generate standardized JSON output.
"""

import sys
import os
from pathlib import Path

# Add the parent directory to the path so we can import pdf_extractor
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pdf_extractor import PDFExtractor


def main():
    """
    Example usage of the PDF extractor.
    """
    # Initialize the extractor
    extractor = PDFExtractor()
    
    # Check if PDF path is provided as command line argument
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
    else:
        # Default example path (user should replace with their PDF)
        pdf_path = "example.pdf"
        print(f"No PDF path provided. Using default: {pdf_path}")
        print("Usage: python example_usage.py <path_to_pdf>")
        print()
    
    # Check if file exists
    if not os.path.exists(pdf_path):
        print(f"Error: PDF file not found: {pdf_path}")
        print("Please provide a valid path to a PDF file.")
        return
    
    # Optional: specify custom output path
    # If not specified, output will be saved as <pdf_name>_extracted.json
    output_path = None
    if len(sys.argv) > 2:
        output_path = sys.argv[2]
    
    try:
        print(f"Extracting content from: {pdf_path}")
        print("This may take a moment...")
        print()
        
        # Extract content
        result = extractor.extract(pdf_path, output_path)
        
        # Display summary
        print("Extraction completed successfully!")
        print(f"Document ID: {result['document_id']}")
        print(f"Total pages: {result['total_pages']}")
        print()
        
        # Show statistics per page
        for page in result['pages']:
            page_num = page['page_number']
            print(f"Page {page_num}:")
            print(f"  - Tables: {len(page['tables'])}")
            print(f"  - Charts: {len(page['charts'])}")
            print(f"  - Images: {len(page['images'])}")
            print(f"  - Titles: {len(page['text']['titles'])}")
            print(f"  - Subtitles: {len(page['text']['subtitles'])}")
            print(f"  - Body text blocks: {len(page['text']['body'])}")
            print(f"  - Citations: {len(page['text']['citations'])}")
            print()
        
        # Show output file location
        if output_path:
            print(f"Output saved to: {output_path}")
        else:
            default_output = os.path.join(
                os.path.dirname(pdf_path),
                f"{result['document_id']}_extracted.json"
            )
            print(f"Output saved to: {default_output}")
        
        print()
        print("JSON file is ready for multilingual processing and semantic interpretation.")
        
    except Exception as e:
        print(f"Error during extraction: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

