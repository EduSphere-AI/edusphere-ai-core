# pdf_course_extractor_summarization/image_processor.py

import os
from typing import Dict, Any, List

import pytesseract
from PIL import Image, ImageDraw

from .config import Config


class ImageProcessor:


    def __init__(self, output_dir: str = Config.DEFAULT_OUTPUT_DIR):
        self.output_dir = output_dir
        self.img_dir = os.path.join(output_dir, Config.IMAGES_DIR_NAME)
        os.makedirs(self.img_dir, exist_ok=True)


    def process_image(self, image_path: str, block_id: int) -> Dict[str, Any]:

        if not os.path.exists(image_path):

            return {
                "ocr_text": "",
                "ocr_items": [],
                "masked_image_path": None,
            }

        img = Image.open(image_path).convert("RGB")


        ocr_items = self._run_ocr(img)


        masked_path = self._mask_text(img, ocr_items, block_id)


        ocr_text = " ".join(item["text"] for item in ocr_items if item["text"])

        return {
            "ocr_text": ocr_text,
            "ocr_items": ocr_items,
            "masked_image_path": masked_path,
        }


    def _run_ocr(self, img: Image.Image) -> List[Dict[str, Any]]:

        data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)

        items: List[Dict[str, Any]] = []
        n = len(data.get("text", []))

        for i in range(n):
            text = (data["text"][i] or "").strip()
            if not text:
                continue

            try:
                x = int(data["left"][i])
                y = int(data["top"][i])
                w = int(data["width"][i])
                h = int(data["height"][i])
            except Exception:

                continue

            items.append(
                {
                    "text": text,
                    "left": x,
                    "top": y,
                    "width": w,
                    "height": h,
                    "conf": float(data.get("conf", ["0"] * n)[i]),
                    "line_num": int(data.get("line_num", ["0"] * n)[i]),
                    "word_num": int(data.get("word_num", ["0"] * n)[i]),
                }
            )

        return items


    def _mask_text(
        self,
        img: Image.Image,
        ocr_items: List[Dict[str, Any]],
        block_id: int,
    ) -> str | None:

        if not ocr_items:
            return None

        draw = ImageDraw.Draw(img)

        for item in ocr_items:
            x = item["left"]
            y = item["top"]
            w = item["width"]
            h = item["height"]


            pad = 2
            draw.rectangle(
                [x - pad, y - pad, x + w + pad, y + h + pad],
                fill="white",
                outline="white",
            )

        masked_filename = f"block_{block_id}_masked.png"
        masked_path = os.path.join(self.img_dir, masked_filename)
        img.save(masked_path)

        return masked_path