import os
import logging
import json
import uuid
from typing import List, Dict, Any, Optional
from pdf2docx import Converter
from docx import Document
from docx.document import Document as _Document
from docx.oxml.text.paragraph import CT_P
from docx.oxml.table import CT_Tbl
from docx.table import Table
from docx.text.paragraph import Paragraph
from PIL import Image, ImageChops

# Import data structures from existing extraction module for consistency
try:
    from features.extraction import ContentElement, ImageContext, TextStyle, ElementType, Position
except ImportError:
    # Fallback if imports fail (e.g. running as script)
    from dataclasses import dataclass, field
    from enum import Enum

    class ElementType(Enum):
        PARAGRAPH = "paragraph"
        TABLE = "table"
        FIGURE = "figure"

    @dataclass
    class Position:
        x0: float = 0.0
        y0: float = 0.0
        x1: float = 0.0
        y1: float = 0.0
        page: int = 0

        def to_dict(self):
            return self.__dict__

    @dataclass
    class TextStyle:
        font_size: float = 11.0
        is_bold: bool = False
        is_italic: bool = False

        def to_dict(self):
            return self.__dict__

    @dataclass
    class ImageContext:
        image_path: str

        def to_dict(self):
            return self.__dict__

    @dataclass
    class ContentElement:
        id: str
        type: str
        content: str
        position: Optional[Position]
        style: TextStyle
        table_data: Optional[List[List[str]]] = None
        image_context: Optional[ImageContext] = None

        def to_dict(self):
            return {
                "id":
                self.id,
                "type":
                self.type,
                "content":
                self.content,
                "table_data":
                self.table_data,
                "image_context":
                self.image_context.to_dict() if self.image_context else None
            }


# Configure logging
logger = logging.getLogger(__name__)


class WordExtractor:
    """
    Extracts content from PDF by first converting it to DOCX.
    Specializes in Table and Image extraction which is often better in DOCX format.
    """

    def __init__(self, pdf_path: str, output_dir: str):
        self.pdf_path = pdf_path
        self.output_dir = output_dir
        self.docx_path = os.path.join(
            output_dir,
            os.path.splitext(os.path.basename(pdf_path))[0] + ".docx")
        self.images_dir = os.path.join(output_dir, "images")
        os.makedirs(self.images_dir, exist_ok=True)

    def convert_pdf_to_docx(self):
        """Convert PDF to DOCX using pdf2docx."""
        if not os.path.exists(self.pdf_path):
            raise FileNotFoundError(f"PDF file not found: {self.pdf_path}")

        logger.info(f"Converting {self.pdf_path} to {self.docx_path}")
        try:
            cv = Converter(self.pdf_path)
            cv.convert(self.docx_path)
            cv.close()
            logger.info("Conversion successful")
        except Exception as e:
            logger.error(f"Failed to convert PDF to DOCX: {e}")
            raise

    def _get_image_from_blip(self, doc: _Document,
                             blip_id: str) -> Optional[str]:
        """Resolve image path from relationship ID."""
        try:
            part = doc.part.related_parts[blip_id]
            # Generate a unique name or use partname
            image_filename = os.path.basename(part.partname)
            # Ensure unique filename to avoid overwrites if multiple parts define same name
            # (though usually unique in package)
            if not image_filename.lower().endswith(
                ('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
                image_filename += ".png"

            save_path = os.path.join(self.images_dir, image_filename)

            # Save if not exists
            if not os.path.exists(save_path):
                with open(save_path, "wb") as f:
                    f.write(part.blob)

            return save_path
        except KeyError:
            return None

    def extract_content(self) -> List[ContentElement]:
        """Extract content (text, tables, images) from DOCX in order."""
        if not os.path.exists(self.docx_path):
            self.convert_pdf_to_docx()

        logger.info(f"Extracting content from {self.docx_path}")
        doc = Document(self.docx_path)
        elements = []

        # Iterate over the document body elements to maintain order
        for element in doc.element.body:
            if isinstance(element, CT_P):
                paragraph = Paragraph(element, doc)

                # 1. Handle Images in Paragraph
                # Iterate through XML to find blip references (images)
                # This captures inline images
                for run in paragraph.runs:
                    xml = run.element.xml
                    if 'a:blip' in xml:
                        # Extract r:embed attribute value
                        # Naive XML parsing or using lxml if available, but string find is faster for simple check
                        # namespace for r is usually http://schemas.openxmlformats.org/officeDocument/2006/relationships
                        # We look for r:embed="..."
                        import re
                        embed_matches = re.findall(r'r:embed="([^"]+)"', xml)
                        for rId in embed_matches:
                            image_path = self._get_image_from_blip(doc, rId)
                            if image_path:
                                elements.append(
                                    ContentElement(
                                        id=str(uuid.uuid4()),
                                        type=ElementType.FIGURE.value,
                                        content=
                                        f"Image extracted from {os.path.basename(image_path)}",
                                        position=None,
                                        style=TextStyle(font_size=11.0),
                                        image_context=ImageContext(
                                            image_path=image_path)))

                # 2. Handle Text
                text = paragraph.text.strip()
                if text:
                    elements.append(
                        ContentElement(
                            id=str(uuid.uuid4()),
                            type=ElementType.PARAGRAPH.value,
                            content=text,
                            position=None,
                            style=TextStyle(
                                font_size=11.0
                            ),  # Could extract bold/italic from runs if needed
                        ))

            elif isinstance(element, CT_Tbl):
                table = Table(element, doc)
                table_data = []
                for row in table.rows:
                    row_data = [cell.text.strip() for cell in row.cells]
                    table_data.append(row_data)

                if table_data:
                    # Create a string representation for content
                    # e.g. CSV-like or just JSON
                    content_str = "\n".join(
                        [" | ".join(row) for row in table_data])

                    elements.append(
                        ContentElement(id=str(uuid.uuid4()),
                                       type=ElementType.TABLE.value,
                                       content=content_str,
                                       position=None,
                                       style=TextStyle(font_size=11.0),
                                       table_data=table_data))

        logger.info(f"Extracted {len(elements)} elements")
        return elements


if __name__ == "__main__":
    # Test block
    import sys
    if len(sys.argv) > 1:
        pdf_file = sys.argv[1]
        extractor = WordExtractor(pdf_file, "output_test")
        elements = extractor.extract_content()
        print(
            json.dumps([e.to_dict() for e in elements], indent=2, default=str))
