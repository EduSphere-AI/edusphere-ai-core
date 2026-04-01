from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
import math

BBox = Tuple[float, float, float, float]


@dataclass
class _BlockRef:
    idx: int
    block: Dict[str, Any]


def _bbox_area(b: BBox) -> float:
    x0, y0, x1, y1 = b
    return max(0.0, x1 - x0) * max(0.0, y1 - y0)


def _bbox_intersection(a: BBox, b: BBox) -> float:
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    ix0 = max(ax0, bx0)
    iy0 = max(ay0, by0)
    ix1 = min(ax1, bx1)
    iy1 = min(ay1, by1)
    if ix1 <= ix0 or iy1 <= iy0:
        return 0.0
    return (ix1 - ix0) * (iy1 - iy0)


def _bbox_overlap_ratio(inner: BBox, outer: BBox) -> float:

    inner_area = _bbox_area(inner)
    if inner_area <= 0:
        return 0.0
    inter = _bbox_intersection(inner, outer)
    return inter / inner_area


def _safe_bbox(block: Dict[str, Any]) -> Optional[BBox]:
    meta = block.get("metadata") or {}
    bbox = meta.get("bbox")
    if not bbox or len(bbox) != 4:
        return None
    try:
        x0, y0, x1, y1 = [float(x) for x in bbox]
    except Exception:
        return None
    return (x0, y0, x1, y1)


def _group_blocks_by_page(blocks: List[Dict[str, Any]]) -> Dict[int, List[_BlockRef]]:
    by_page: Dict[int, List[_BlockRef]] = {}
    for idx, b in enumerate(blocks):
        meta = b.get("metadata") or {}
        page = meta.get("page")
        if page is None:
            page = 0
        by_page.setdefault(int(page), []).append(_BlockRef(idx=idx, block=b))
    return by_page


def _find_existing_figure_bands(blocks: List[Dict[str, Any]]) -> Dict[int, List[_BlockRef]]:
    by_page = _group_blocks_by_page(blocks)
    out: Dict[int, List[_BlockRef]] = {}
    for page, refs in by_page.items():
        for ref in refs:
            meta = ref.block.get("metadata") or {}
            source = meta.get("source") or ""
            if source in ("figure-band", "table-band", "figure-region"):
                out.setdefault(page, []).append(ref)
    return out


def _detect_synthetic_figure_band_for_page(
    page: int,
    page_blocks: List[_BlockRef],
    has_real_figure_band: bool,
    min_vertical_fraction: float = 0.25,
) -> Optional[Dict[str, Any]]:

    if has_real_figure_band:
        return None

    all_boxes: List[BBox] = []
    para_boxes: List[BBox] = []

    for ref in page_blocks:
        b = ref.block
        bbox = _safe_bbox(b)
        if bbox is None:
            continue
        all_boxes.append(bbox)
        if b.get("type") == "paragraph":
            para_boxes.append(bbox)

    if not all_boxes or not para_boxes:
        return None

    xs0 = [b[0] for b in all_boxes]
    ys0 = [b[1] for b in all_boxes]
    xs1 = [b[2] for b in all_boxes]
    ys1 = [b[3] for b in all_boxes]

    page_x0 = min(xs0)
    page_y0 = min(ys0)
    page_x1 = max(xs1)
    page_y1 = max(ys1)

    page_height = page_y1 - page_y0
    if page_height <= 0:
        return None

    para_boxes_sorted = sorted(para_boxes, key=lambda b: b[1])


    last_bottom = para_boxes_sorted[-1][3]
    bottom_gap_start = last_bottom
    bottom_gap_height = page_y1 - bottom_gap_start

    if bottom_gap_height <= 0:
        return None
    if bottom_gap_height < min_vertical_fraction * page_height:
        return None

    synthetic_bbox: BBox = (page_x0, bottom_gap_start, page_x1, page_y1)


    caption_text: Optional[str] = None
    closest_delta = math.inf
    for ref in page_blocks:
        b = ref.block
        if b.get("type") != "paragraph":
            continue
        bbox = _safe_bbox(b)
        if not bbox:
            continue
        _, _, _, y1 = bbox
        if y1 <= bottom_gap_start:
            delta = bottom_gap_start - y1
            if delta < closest_delta:
                closest_delta = delta
                caption_text = (b.get("content") or {}).get("text") or b.get("text")


    snapshot_image: Optional[Dict[str, Any]] = None
    for ref in page_blocks:
        b = ref.block
        if b.get("type") == "page_image":
            meta = b.get("metadata") or {}
            if meta.get("source") == "page_snapshot":
                images = (b.get("content") or {}).get("images") or []
                if images:
                    snapshot_image = dict(images[0])
                    break

    images_payload: List[Dict[str, Any]] = []
    if snapshot_image is not None:
        images_payload.append(snapshot_image)

    content: Dict[str, Any] = {"images": images_payload}
    if caption_text:
        content["caption"] = caption_text

    synthetic_block: Dict[str, Any] = {
        "type": "image",
        "text": "",
        "content": content,
        "metadata": {
            "page": page,
            "bbox": [synthetic_bbox[0], synthetic_bbox[1], synthetic_bbox[2], synthetic_bbox[3]],
            "source": "synthetic-figure-band",
            "ocr_text": caption_text or "",
        },
    }
    return synthetic_block


def _attach_paragraphs_to_figure_bands(
    blocks: List[Dict[str, Any]],
    figure_bands_by_page: Dict[int, List[_BlockRef]],
    overlap_threshold: float = 0.5,
) -> None:

    by_page = _group_blocks_by_page(blocks)

    for page, page_blocks in by_page.items():
        figure_refs = figure_bands_by_page.get(page) or []
        if not figure_refs:
            continue

        figure_boxes: List[Tuple[BBox, _BlockRef]] = []
        for fref in figure_refs:
            fbbox = _safe_bbox(fref.block)
            if fbbox is None:
                continue
            figure_boxes.append((fbbox, fref))

        if not figure_boxes:
            continue

        for ref in page_blocks:
            b = ref.block
            if b.get("type") != "paragraph":
                continue
            pbbox = _safe_bbox(b)
            if pbbox is None:
                continue

            best_overlap = 0.0
            best_fref: Optional[_BlockRef] = None

            for fbbox, fref in figure_boxes:
                ov = _bbox_overlap_ratio(pbbox, fbbox)
                if ov > best_overlap:
                    best_overlap = ov
                    best_fref = fref

            if best_overlap >= overlap_threshold and best_fref is not None:
                # Re-type this block as figure_paragraph
                b["type"] = "figure_paragraph"
                meta = b.setdefault("metadata", {})
                meta["inside_figure_band"] = True

                f_content = best_fref.block.setdefault("content", {})
                attached_ids = f_content.setdefault("attached_paragraph_ids", [])
                para_id = b.get("id", ref.idx)
                if para_id not in attached_ids:
                    attached_ids.append(para_id)


def enhance_figures_and_tables(db: Dict[str, Any]) -> Dict[str, Any]:

    document = db.get("document") or {}
    blocks: List[Dict[str, Any]] = document.get("content_blocks") or []

    if not blocks:
        return db


    figure_bands_by_page = _find_existing_figure_bands(blocks)


    by_page = _group_blocks_by_page(blocks)

    max_id = -1
    for b in blocks:
        if "id" in b and isinstance(b["id"], int):
            if b["id"] > max_id:
                max_id = b["id"]

    new_blocks: List[Dict[str, Any]] = []

    for page, page_blocks in by_page.items():
        has_real = bool(figure_bands_by_page.get(page))
        synthetic = _detect_synthetic_figure_band_for_page(
            page=page,
            page_blocks=page_blocks,
            has_real_figure_band=has_real,
        )
        if synthetic is not None:
            max_id += 1
            synthetic["id"] = max_id
            new_blocks.append(synthetic)
            figure_bands_by_page.setdefault(page, []).append(
                _BlockRef(idx=len(blocks) + len(new_blocks) - 1, block=synthetic)
            )

    if new_blocks:
        blocks.extend(new_blocks)
        document["content_blocks"] = blocks
        db["document"] = document


    _attach_paragraphs_to_figure_bands(blocks, figure_bands_by_page)

    return db