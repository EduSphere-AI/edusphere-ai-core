"""
PDF Content Extractor

A modular Python package for extracting and standardizing content from academic PDFs
without using OCR. Extracts tables, charts, images, and text in a structured format.
"""

from .extractor import PDFExtractor

__version__ = "1.0.0"
__all__ = ["PDFExtractor"]

