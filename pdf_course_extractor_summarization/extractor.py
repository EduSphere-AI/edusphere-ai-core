# pdf_course_extractor_summarization/extractor.py
import os

import fitz

from .config import Config


try:
    import cv2
    import numpy as np
except Exception:
    cv2 = None
    np = None


class ContentBlock:
    def __init__(self, block_id, type, text="", content=None, metadata=None):
        self.id = block_id
        self.type = type
        self.text = text
        self.content = content if content is not None else {}
        self.metadata = metadata if metadata is not None else {}


class PDFExtractor:
    def __init__(self, pdf_path, output_dir=Config.DEFAULT_OUTPUT_DIR):
        self.pdf_path = pdf_path
        self.output_dir = output_dir
        self.image_dir = os.path.join(output_dir, Config.IMAGES_DIR_NAME)

        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.image_dir, exist_ok=True)

        self.doc = fitz.open(pdf_path)
        self.blocks = []
        self.block_counter = 1


    def analyze_font_attributes(self, span):
        size = span.get("size", 0)
        flags = span.get("flags", 0)
        font = span.get("font", "")
        is_bold = bool(flags & 2**4)
        is_italic = bool(flags & 2**1)
        return size, is_bold, is_italic, font

    def determine_type(self, text, formatting):

        size = formatting.get("size", 0)
        is_bold = formatting.get("bold", False)

        lower_text = text.lower().strip()

        if lower_text.startswith(("figure", "fig.", "table", "map ", "chart ", "diagram ")):
            return "caption"

        if size >= Config.TITLE_FONT_SIZE_THRESHOLD:
            return "title"
        if size >= Config.CHAPTER_FONT_SIZE_THRESHOLD:
            return "chapter-title"
        if size >= Config.SUBCHAPTER_FONT_SIZE_THRESHOLD and is_bold:
            return "subchapter-title"

        return "paragraph"


    def extract_content(self):

        print(f"Processing PDF: {self.pdf_path}")

        for page_num, page in enumerate(self.doc):
            page_dict = page.get_text("dict")


            for block in page_dict.get("blocks", []):
                if block["type"] == 0:
                    self._process_text_block(block, page_num)
                elif block["type"] == 1:
                    self._process_image_block(block, page_num)


            self._add_page_snapshot(page, page_num)


            self._extract_figure_regions(page, page_num)

        return self.blocks


    def _process_text_block(self, block, page_num):

        block_text = ""
        primary_formatting = {}

        for line in block.get("lines", []):
            for span in line.get("spans", []):
                if not primary_formatting:
                    size, bold, italic, font = self.analyze_font_attributes(span)
                    primary_formatting = {
                        "size": size,
                        "bold": bold,
                        "italic": italic,
                        "font": font,
                    }
                block_text += span.get("text", "") + " "

        block_text = block_text.strip()
        if not block_text:
            return

        block_type = self.determine_type(block_text, primary_formatting)

        content_block = ContentBlock(
            block_id=self.block_counter,
            type=block_type,
            text=block_text,
            content={},
            metadata={
                "page": page_num + 1,
                "bbox": block.get("bbox", None),
                "formatting": primary_formatting,
            },
        )
        self.blocks.append(content_block)
        self.block_counter += 1


    def _process_image_block(self, block, page_num):

        ext = block.get("ext", "png")
        img_bytes = block.get("image", None)
        if not img_bytes:
            return

        filename = f"img_{self.block_counter}.{ext}"
        filepath = os.path.join(self.image_dir, filename)

        with open(filepath, "wb") as f:
            f.write(img_bytes)

        content_block = ContentBlock(
            block_id=self.block_counter,
            type="image",
            text="",
            content={"images": [{"filename": filename, "path": filepath}]},
            metadata={
                "page": page_num + 1,
                "bbox": block.get("bbox", None),
                "source": "inline-image",
            },
        )
        self.blocks.append(content_block)
        self.block_counter += 1


    def _add_page_snapshot(self, page, page_num, scale: float = 2.0):

        mat = fitz.Matrix(scale, scale)
        pix = page.get_pixmap(matrix=mat)

        filename = f"page_{page_num + 1}_snapshot.png"
        filepath = os.path.join(self.image_dir, filename)
        pix.save(filepath)

        content_block = ContentBlock(
            block_id=self.block_counter,
            type="page_image",
            text="",
            content={"images": [{"filename": filename, "path": filepath}]},
            metadata={
                "page": page_num + 1,
                "source": "page_snapshot",
                "width": pix.width,
                "height": pix.height,
            },
        )
        self.blocks.append(content_block)
        self.block_counter += 1


    def _extract_figure_regions(self, page, page_num):

        captions = []
        for b in self.blocks:
            if (
                b.metadata.get("page") == page_num + 1
                and b.type == "caption"
                and b.metadata.get("bbox") is not None
            ):
                captions.append(b)

        page_rect = page.rect

        for cap in captions:
            bbox = cap.metadata.get("bbox")
            if not bbox:
                continue

            cap_rect = fitz.Rect(bbox)


            band_height = page_rect.height * 0.18
            top = max(page_rect.y0, cap_rect.y0 - band_height)
            bottom = min(page_rect.y1, cap_rect.y1 + band_height)
            left = page_rect.x0
            right = page_rect.x1
            band_rect = fitz.Rect(left, top, right, bottom)

            if band_rect.height < 20:
                continue


            if cv2 is not None and np is not None:
                sub_rects = self._split_region_via_contours(page, band_rect)
                if sub_rects:
                    for r in sub_rects:
                        self._save_region_image(
                            page,
                            r,
                            page_num,
                            caption_text=cap.text,
                            source="figure-region",
                        )

                    continue


            self._save_region_image(
                page,
                band_rect,
                page_num,
                caption_text=cap.text,
                source="figure-band",
            )


        self._extract_captionless_figure_regions(page, page_num)

    def _extract_captionless_figure_regions(
        self,
        page,
        page_num: int,
        min_gap_height_ratio: float = 0.18,
    ):

        page_index = page_num + 1


        has_figure_images = any(
            b.metadata.get("page") == page_index
            and b.type == "image"
            and b.metadata.get("source") in (
                "figure-band",
                "figure-region",
                "figure-captionless",
            )
            for b in self.blocks
        )
        if has_figure_images:
            return


        textish_types = {
            "paragraph",
            "figure_paragraph",
            "caption",
            "title",
            "chapter-title",
            "subchapter-title",
        }

        text_boxes = []
        for b in self.blocks:
            if b.metadata.get("page") != page_index:
                continue
            if b.type not in textish_types:
                continue
            bbox = b.metadata.get("bbox")
            if not bbox:
                continue
            x0, y0, x1, y1 = bbox
            if x1 <= x0 or y1 <= y0:
                continue
            text_boxes.append((float(x0), float(y0), float(x1), float(y1)))


        if len(text_boxes) < 2:
            return

        page_rect = page.rect


        def rect_area(x0, y0, x1, y1) -> float:
            return max(0.0, x1 - x0) * max(0.0, y1 - y0)

        created_any = False


        spans = sorted((y0, y1) for (_, y0, _, y1) in text_boxes)
        gaps = []
        cursor = float(page_rect.y0)

        for top, bottom in spans:
            if top - cursor > 5:
                gaps.append((cursor, top))
            cursor = max(cursor, bottom)


        if page_rect.y1 - cursor > 5:
            gaps.append((cursor, page_rect.y1))

        for gap_top, gap_bottom in gaps:
            gap_height = gap_bottom - gap_top
            if gap_height < page_rect.height * float(min_gap_height_ratio):
                continue


            left = page_rect.x0 + 0.08 * page_rect.width
            right = page_rect.x1 - 0.08 * page_rect.width
            band_rect = fitz.Rect(left, gap_top, right, gap_bottom)

            band_area = rect_area(band_rect.x0, band_rect.y0, band_rect.x1, band_rect.y1)
            if band_area <= 0:
                continue


            overlap_area = 0.0
            for x0, y0, x1, y1 in text_boxes:
                ix0 = max(x0, band_rect.x0)
                iy0 = max(y0, band_rect.y0)
                ix1 = min(x1, band_rect.x1)
                iy1 = min(y1, band_rect.y1)
                overlap_area += rect_area(ix0, iy0, ix1, iy1)

            if band_area <= 0:
                continue

            if overlap_area / band_area > 0.15:
                continue

            if band_rect.height < 32 or band_rect.width < 64:
                continue

            self._save_region_image(
                page,
                band_rect,
                page_num,
                caption_text="",
                source="figure-captionless",
            )
            created_any = True


        if created_any:
            return


        mid_top = page_rect.y0 + 0.30 * page_rect.height
        mid_bottom = page_rect.y0 + 0.75 * page_rect.height
        if mid_bottom <= mid_top:
            return

        left = page_rect.x0 + 0.08 * page_rect.width
        right = page_rect.x1 - 0.08 * page_rect.width
        band_rect = fitz.Rect(left, mid_top, right, mid_bottom)

        band_area = rect_area(band_rect.x0, band_rect.y0, band_rect.x1, band_rect.y1)
        if band_area <= 0:
            return

        overlap_area = 0.0
        for x0, y0, x1, y1 in text_boxes:
            ix0 = max(x0, band_rect.x0)
            iy0 = max(y0, band_rect.y0)
            ix1 = min(x1, band_rect.x1)
            iy1 = min(y1, band_rect.y1)
            overlap_area += rect_area(ix0, iy0, ix1, iy1)

        text_fraction = overlap_area / band_area


        if text_fraction >= 0.4:
            return

        if band_rect.height < 32 or band_rect.width < 64:
            return

        self._save_region_image(
            page,
            band_rect,
            page_num,
            caption_text="",
            source="figure-captionless",
        )

    def _split_region_via_contours(self, page, band_rect, min_area_ratio: float = 0.02):

        if cv2 is None or np is None:
            return []

        mat = fitz.Matrix(2.0, 2.0)
        pix = page.get_pixmap(matrix=mat, clip=band_rect)


        img = np.frombuffer(pix.samples, dtype=np.uint8)
        img = img.reshape(pix.height, pix.width, pix.n)

        if pix.n == 4:
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blur, 50, 150)

        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        dilated = cv2.dilate(edges, kernel, iterations=1)

        contours, _ = cv2.findContours(
            dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        h, w = gray.shape
        min_area = min_area_ratio * h * w

        rects = []
        for cnt in contours:
            x, y, ww, hh = cv2.boundingRect(cnt)
            area = ww * hh
            if area < min_area:
                continue


            if ww > 0.95 * w and hh > 0.95 * h:
                continue


            x0 = band_rect.x0 + (x / w) * band_rect.width
            y0 = band_rect.y0 + (y / h) * band_rect.height
            x1 = band_rect.x0 + ((x + ww) / w) * band_rect.width
            y1 = band_rect.y0 + ((y + hh) / h) * band_rect.height

            rects.append(fitz.Rect(x0, y0, x1, y1))

        return rects

    def _save_region_image(
        self,
        page,
        rect: fitz.Rect,
        page_num: int,
        caption_text: str = "",
        source: str = "figure-region",
        scale: float = 2.0,
    ):

        mat = fitz.Matrix(scale, scale)
        pix = page.get_pixmap(matrix=mat, clip=rect)
        if pix.width < Config.MIN_IMAGE_WIDTH or pix.height < Config.MIN_IMAGE_HEIGHT:
            return

        filename = f"figure_{page_num + 1}_{self.block_counter}.png"
        filepath = os.path.join(self.image_dir, filename)
        pix.save(filepath)

        content_block = ContentBlock(
            block_id=self.block_counter,
            type="image",
            text="",
            content={
                "images": [{"filename": filename, "path": filepath}],
                "caption": caption_text,
            },
            metadata={
                "page": page_num + 1,
                "bbox": [rect.x0, rect.y0, rect.x1, rect.y1],
                "source": source,
            },
        )
        self.blocks.append(content_block)
        self.block_counter += 1