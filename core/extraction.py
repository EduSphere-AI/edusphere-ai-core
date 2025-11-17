"""
PDF Extraction Module

This module provides functionality to extract various elements from PDF files,
including text, tables, images, and metadata. It supports both local and remote PDFs.
"""

import io
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from urllib.parse import urlparse
import requests
import pdfplumber
from pdfplumber.page import Page

logger = logging.getLogger(__name__)


class PDFExtractor:
    """
    A comprehensive PDF extraction class that handles both local and cloud-based PDFs.
    
    Attributes:
        pdf_path (str): Path or URL to the PDF file
        is_remote (bool): Whether the PDF is hosted remotely
    """

    def __init__(self, pdf_path: str):
        """
        Initialize the PDF extractor.
        
        Args:
            pdf_path (str): Local file path or URL (http/https) to the PDF
        """
        self.pdf_path = pdf_path
        self.is_remote = self._is_url(pdf_path)

    def _is_url(self, path: str) -> bool:
        """
        Check if the provided path is a URL.
        
        Args:
            path (str): Path to check
            
        Returns:
            bool: True if path is a URL (http/https), False otherwise
        """
        try:
            result = urlparse(path)
            return result.scheme in ('http', 'https')
        except Exception:
            return False

    def _get_pdf_file(self) -> Union[str, io.BytesIO]:
        """
        Get the PDF file, downloading it if it's remote.
        
        Returns:
            Union[str, io.BytesIO]: File path for local files or BytesIO object for remote files
            
        Raises:
            requests.RequestException: If downloading remote PDF fails
            FileNotFoundError: If local PDF file doesn't exist
        """
        if self.is_remote:
            logger.info(f"Downloading PDF from: {self.pdf_path}")
            try:
                response = requests.get(self.pdf_path, timeout=30)
                response.raise_for_status()
                return io.BytesIO(response.content)
            except requests.RequestException as e:
                logger.error(f"Failed to download PDF: {e}")
                raise
        else:
            if not Path(self.pdf_path).exists():
                raise FileNotFoundError(f"PDF file not found: {self.pdf_path}")
            return self.pdf_path

    def extract_text(self,
                     page_numbers: Optional[List[int]] = None
                     ) -> Dict[int, str]:
        """
        Extract text from PDF pages.
        
        Args:
            page_numbers (Optional[List[int]]): Specific page numbers to extract (0-indexed).
                                                If None, extracts from all pages.
        
        Returns:
            Dict[int, str]: Dictionary mapping page numbers to extracted text
        """
        extracted_text = {}
        pdf_file = self._get_pdf_file()

        try:
            with pdfplumber.open(pdf_file) as pdf:
                pages_to_process = page_numbers if page_numbers else range(
                    len(pdf.pages))

                for page_num in pages_to_process:
                    if page_num < len(pdf.pages):
                        page = pdf.pages[page_num]
                        text = page.extract_text() or ""
                        extracted_text[page_num] = text
                    else:
                        logger.warning(
                            f"Page {page_num} does not exist in PDF")

            logger.info(f"Extracted text from {len(extracted_text)} pages")
            return extracted_text

        except Exception as e:
            logger.error(f"Error extracting text: {e}")
            raise

    def extract_tables(
        self,
        page_numbers: Optional[List[int]] = None
    ) -> Dict[int, List[List[List[str]]]]:
        """
        Extract tables from PDF pages.
        
        Args:
            page_numbers (Optional[List[int]]): Specific page numbers to extract (0-indexed).
                                                If None, extracts from all pages.
        
        Returns:
            Dict[int, List[List[List[str]]]]: Dictionary mapping page numbers to list of tables,
                                              where each table is a list of rows
        """
        extracted_tables = {}
        pdf_file = self._get_pdf_file()

        try:
            with pdfplumber.open(pdf_file) as pdf:
                pages_to_process = page_numbers if page_numbers else range(
                    len(pdf.pages))

                for page_num in pages_to_process:
                    if page_num < len(pdf.pages):
                        page = pdf.pages[page_num]
                        tables = page.extract_tables()
                        if tables:
                            extracted_tables[page_num] = tables
                    else:
                        logger.warning(
                            f"Page {page_num} does not exist in PDF")

            logger.info(f"Extracted tables from {len(extracted_tables)} pages")
            return extracted_tables

        except Exception as e:
            logger.error(f"Error extracting tables: {e}")
            raise

    def extract_images(
        self,
        page_numbers: Optional[List[int]] = None
    ) -> Dict[int, List[Dict[str, Any]]]:
        """
        Extract image information from PDF pages.
        
        Args:
            page_numbers (Optional[List[int]]): Specific page numbers to extract (0-indexed).
                                                If None, extracts from all pages.
        
        Returns:
            Dict[int, List[Dict[str, Any]]]: Dictionary mapping page numbers to list of image info
        """
        extracted_images = {}
        pdf_file = self._get_pdf_file()

        try:
            with pdfplumber.open(pdf_file) as pdf:
                pages_to_process = page_numbers if page_numbers else range(
                    len(pdf.pages))

                for page_num in pages_to_process:
                    if page_num < len(pdf.pages):
                        page = pdf.pages[page_num]
                        images = page.images
                        if images:
                            extracted_images[page_num] = images
                    else:
                        logger.warning(
                            f"Page {page_num} does not exist in PDF")

            logger.info(f"Extracted images from {len(extracted_images)} pages")
            return extracted_images

        except Exception as e:
            logger.error(f"Error extracting images: {e}")
            raise

    def extract_metadata(self) -> Dict[str, Any]:
        """
        Extract PDF metadata.
        
        Returns:
            Dict[str, Any]: Dictionary containing PDF metadata
        """
        pdf_file = self._get_pdf_file()

        try:
            with pdfplumber.open(pdf_file) as pdf:
                metadata = pdf.metadata or {}
                metadata['num_pages'] = len(pdf.pages)

            logger.info("Extracted PDF metadata")
            return metadata

        except Exception as e:
            logger.error(f"Error extracting metadata: {e}")
            raise

    def extract_all(self,
                    page_numbers: Optional[List[int]] = None
                    ) -> Dict[str, Any]:
        """
        Extract all elements from PDF (text, tables, images, and metadata).
        
        Args:
            page_numbers (Optional[List[int]]): Specific page numbers to extract (0-indexed).
                                                If None, extracts from all pages.
        
        Returns:
            Dict[str, Any]: Dictionary containing all extracted elements:
                - 'text': Extracted text per page
                - 'tables': Extracted tables per page
                - 'images': Extracted images per page
                - 'metadata': PDF metadata
        """
        logger.info(f"Starting full extraction from: {self.pdf_path}")

        result = {
            'text': self.extract_text(page_numbers),
            'tables': self.extract_tables(page_numbers),
            'images': self.extract_images(page_numbers),
            'metadata': self.extract_metadata()
        }

        logger.info("Full extraction completed")
        return result

    def get_page_count(self) -> int:
        """
        Get the total number of pages in the PDF.
        
        Returns:
            int: Total number of pages
        """
        pdf_file = self._get_pdf_file()

        try:
            with pdfplumber.open(pdf_file) as pdf:
                return len(pdf.pages)
        except Exception as e:
            logger.error(f"Error getting page count: {e}")
            raise


def extract_pdf(pdf_path: str,
                extract_text: bool = True,
                extract_tables: bool = True,
                extract_images: bool = True,
                extract_metadata: bool = True,
                page_numbers: Optional[List[int]] = None) -> Dict[str, Any]:
    """
    Convenience function to extract elements from a PDF.
    
    Args:
        pdf_path (str): Local file path or URL (http/https) to the PDF
        extract_text (bool): Whether to extract text
        extract_tables (bool): Whether to extract tables
        extract_images (bool): Whether to extract images
        extract_metadata (bool): Whether to extract metadata
        page_numbers (Optional[List[int]]): Specific page numbers to extract (0-indexed)
    
    Returns:
        Dict[str, Any]: Dictionary containing requested extracted elements
        
    Example:
        >>> # Extract from local PDF
        >>> data = extract_pdf('/path/to/document.pdf')
        >>> 
        >>> # Extract from cloud PDF
        >>> data = extract_pdf('https://example.com/document.pdf')
        >>>
        >>> # Extract only text from specific pages
        >>> data = extract_pdf('/path/to/document.pdf', 
        ...                    extract_tables=False,
        ...                    extract_images=False,
        ...                    page_numbers=[0, 1, 2])
    """
    extractor = PDFExtractor(pdf_path)
    result = {}

    if extract_text:
        result['text'] = extractor.extract_text(page_numbers)

    if extract_tables:
        result['tables'] = extractor.extract_tables(page_numbers)

    if extract_images:
        result['images'] = extractor.extract_images(page_numbers)

    if extract_metadata:
        result['metadata'] = extractor.extract_metadata()

    return result
