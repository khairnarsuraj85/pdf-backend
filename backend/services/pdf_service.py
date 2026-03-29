from __future__ import annotations

import io
import re
from typing import Iterable

import fitz
from PIL import Image
from backend.utils.errors import PdfProcessingError, RequestValidationError

COMPRESSION_PRESETS = {
    "light": [
        {"dpi": 160, "quality": 84, "grayscale": False, "monochrome": False, "format": "jpeg"},
        {"dpi": 150, "quality": 80, "grayscale": False, "monochrome": False, "format": "jpeg"},
    ],
    "balanced": [
        {"dpi": 144, "quality": 78, "grayscale": False, "monochrome": False, "format": "jpeg"},
        {"dpi": 132, "quality": 72, "grayscale": False, "monochrome": False, "format": "jpeg"},
        {"dpi": 120, "quality": 66, "grayscale": False, "monochrome": False, "format": "jpeg"},
    ],
    "strong": [
        {"dpi": 120, "quality": 62, "grayscale": False, "monochrome": False, "format": "jpeg"},
        {"dpi": 108, "quality": 56, "grayscale": False, "monochrome": False, "format": "jpeg"},
        {"dpi": 96, "quality": 50, "grayscale": False, "monochrome": False, "format": "jpeg"},
        {"dpi": 84, "quality": 44, "grayscale": False, "monochrome": False, "format": "jpeg"},
    ],
}

COMPRESSION_MODES = {"preserve-quality", "fit-target"}
LATEX_FONT_MARKERS = (
    "cmr",
    "cmmi",
    "cmsy",
    "cmbx",
    "cmex",
    "cmss",
    "cmti",
    "latinmodern",
    "lmodern",
    "computer modern",
)
LATEX_TEXT_PATTERNS = (
    r"\\(?:frac|sum|int|alpha|beta|gamma|delta|theta|lambda|mu|sigma|pi|sqrt|cdot|mathrm|mathbf)\b",
    r"\b(?:theorem|lemma|corollary|proof|proposition|equation|algorithm)\b",
)
MATH_SYMBOL_PATTERN = re.compile(r"[=+\-/*^_<>]|[∑∫√∞≈≠≤≥±×÷α-ωΑ-Ω]")
EQUATION_LINE_PATTERN = re.compile(r"[=+\-/*^_<>()[\]{}]")

WHATSAPP_PRESETS = [
    {"dpi": 108, "quality": 58, "grayscale": False, "monochrome": False, "format": "jpeg"},
    {"dpi": 96, "quality": 50, "grayscale": False, "monochrome": False, "format": "jpeg"},
    {"dpi": 84, "quality": 44, "grayscale": False, "monochrome": False, "format": "jpeg"},
]

IMAGE_RECOMPRESSION_PRESETS = [
    {"max_side": 2200, "quality": 82, "grayscale": False},
    {"max_side": 1800, "quality": 76, "grayscale": False},
    {"max_side": 1500, "quality": 70, "grayscale": False},
    {"max_side": 1200, "quality": 62, "grayscale": False},
    {"max_side": 1000, "quality": 54, "grayscale": False},
    {"max_side": 900, "quality": 48, "grayscale": True},
]

FIT_TARGET_CANDIDATES = {
    "text": [
        {"dpi": 120, "quality": 50, "grayscale": True, "monochrome": False, "format": "jpeg"},
        {"dpi": 96, "quality": 42, "grayscale": True, "monochrome": False, "format": "jpeg"},
        {"dpi": 84, "quality": 36, "grayscale": True, "monochrome": False, "format": "jpeg"},
        {"dpi": 72, "quality": 30, "grayscale": True, "monochrome": False, "format": "jpeg"},
        {"dpi": 60, "quality": 24, "grayscale": True, "monochrome": False, "format": "jpeg"},
        {"dpi": 72, "quality": 0, "grayscale": False, "monochrome": True, "format": "png"},
        {"dpi": 60, "quality": 0, "grayscale": False, "monochrome": True, "format": "png"},
        {"dpi": 48, "quality": 0, "grayscale": False, "monochrome": True, "format": "png"},
        {"dpi": 36, "quality": 0, "grayscale": False, "monochrome": True, "format": "png"},
        {"dpi": 30, "quality": 0, "grayscale": False, "monochrome": True, "format": "png"},
        {"dpi": 24, "quality": 0, "grayscale": False, "monochrome": True, "format": "png"},
    ],
    "mixed": [
        {"dpi": 132, "quality": 72, "grayscale": False, "monochrome": False, "format": "jpeg"},
        {"dpi": 120, "quality": 66, "grayscale": False, "monochrome": False, "format": "jpeg"},
        {"dpi": 108, "quality": 58, "grayscale": False, "monochrome": False, "format": "jpeg"},
        {"dpi": 96, "quality": 50, "grayscale": False, "monochrome": False, "format": "jpeg"},
        {"dpi": 84, "quality": 42, "grayscale": False, "monochrome": False, "format": "jpeg"},
        {"dpi": 72, "quality": 34, "grayscale": True, "monochrome": False, "format": "jpeg"},
        {"dpi": 60, "quality": 26, "grayscale": True, "monochrome": False, "format": "jpeg"},
        {"dpi": 54, "quality": 22, "grayscale": True, "monochrome": False, "format": "jpeg"},
        {"dpi": 48, "quality": 20, "grayscale": True, "monochrome": False, "format": "jpeg"},
        {"dpi": 36, "quality": 20, "grayscale": True, "monochrome": False, "format": "jpeg"},
    ],
    "image": [
        {"dpi": 150, "quality": 80, "grayscale": False, "monochrome": False, "format": "jpeg"},
        {"dpi": 132, "quality": 72, "grayscale": False, "monochrome": False, "format": "jpeg"},
        {"dpi": 120, "quality": 66, "grayscale": False, "monochrome": False, "format": "jpeg"},
        {"dpi": 108, "quality": 58, "grayscale": False, "monochrome": False, "format": "jpeg"},
        {"dpi": 96, "quality": 50, "grayscale": False, "monochrome": False, "format": "jpeg"},
        {"dpi": 84, "quality": 42, "grayscale": False, "monochrome": False, "format": "jpeg"},
        {"dpi": 72, "quality": 34, "grayscale": False, "monochrome": False, "format": "jpeg"},
        {"dpi": 60, "quality": 28, "grayscale": False, "monochrome": False, "format": "jpeg"},
    ],
}


def inspect_pdf(file_bytes: bytes) -> dict:
    document = _open_pdf(file_bytes)
    try:
        summary = _summarize_document(document)
        return {
            "pageCount": summary["page_count"],
            "sizeBytes": len(file_bytes),
            "sizeKB": round(len(file_bytes) / 1024, 2),
            "hasImages": summary["image_count"] > 0,
            "imageCount": summary["image_count"],
            "textDensity": "text-heavy" if summary["text_heavy"] else "mixed",
            "textSample": summary["text_sample"][:12000],
            "documentType": summary["document_type"],
            "latexLike": summary["document_type"] == "latex-like",
            "preferSharpText": summary["prefer_sharp_text"],
        }
    finally:
        document.close()


def extract_page_map(file_bytes: bytes, max_pages: int | None = None) -> list[dict]:
    document = _open_pdf(file_bytes)
    try:
        page_map = []
        limit = min(document.page_count, max_pages) if max_pages else document.page_count
        for page_index in range(limit):
            raw_text = document[page_index].get_text("text")
            lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
            excerpt = "\n".join(lines[:8])[:800]
            page_map.append(
                {
                    "page": page_index + 1,
                    "text": excerpt,
                }
            )
        return page_map
    finally:
        document.close()


def compress_pdf(
    file_bytes: bytes,
    compression_level: str = "balanced",
    target_size_kb: int | None = None,
    whatsapp_ready: bool = False,
    compression_mode: str | None = None,
) -> dict:
    compression_level = compression_level if compression_level in COMPRESSION_PRESETS else "balanced"
    compression_mode = _normalize_compression_mode(compression_mode, target_size_kb)
    explicit_target_size_bytes = target_size_kb * 1024 if target_size_kb else None
    decision_target_bytes = explicit_target_size_bytes
    if decision_target_bytes is None and whatsapp_ready and compression_mode == "fit-target":
        decision_target_bytes = 280 * 1024

    document = _open_pdf(file_bytes)
    try:
        summary = _summarize_document(document)
        page_count = summary["page_count"]
        structural_bytes = _try_save_optimized_pdf(document, fallback_bytes=file_bytes)
    finally:
        document.close()

    if len(structural_bytes) > len(file_bytes):
        structural_bytes = file_bytes

    original_size = len(file_bytes)
    preserve_candidates = _build_image_recompression_candidates(
        summary,
        compression_level,
        whatsapp_ready,
        target_size_bytes=decision_target_bytes,
        original_size=original_size,
    )
    best_bytes = _choose_best_image_recompression(
        file_bytes,
        structural_bytes,
        preserve_candidates,
        target_size_bytes=decision_target_bytes,
    )

    strategy = "vector-safe"
    can_rasterize = _should_allow_raster_fallback(
        summary,
        compression_mode,
        compression_level,
        whatsapp_ready,
        decision_target_bytes,
        original_size,
    )
    if (
        compression_mode == "fit-target"
        and decision_target_bytes is not None
        and len(best_bytes) > decision_target_bytes
        and can_rasterize
    ):
        active_candidates = _build_fit_target_candidates(
            summary,
            compression_level,
            whatsapp_ready,
            target_size_bytes=decision_target_bytes,
            original_size=original_size,
        )
        fitted_bytes = _choose_best_compression(
            file_bytes,
            best_bytes,
            active_candidates,
            decision_target_bytes,
        )
        if len(fitted_bytes) <= len(best_bytes):
            best_bytes = fitted_bytes
            strategy = "page-raster"

    processed_size = len(best_bytes)
    compression_ratio = 1 - (processed_size / original_size if original_size else 1)
    target_achieved = _is_target_achieved(processed_size, explicit_target_size_bytes)

    return {
        "bytes": best_bytes,
        "page_count": page_count,
        "original_size": original_size,
        "processed_size": processed_size,
        "compression_ratio": max(compression_ratio, 0),
        "requested_target_kb": target_size_kb,
        "target_achieved": target_achieved,
        "mode": compression_mode,
        "strategy": strategy,
        "profile": summary["profile"],
        "document_type": summary["document_type"],
        "text_priority": summary["prefer_sharp_text"],
    }


def _summarize_document(document: fitz.Document) -> dict:
    analysis = _analyze_document(document)
    text_sample = analysis["text_sample"]
    page_count = document.page_count or 1
    text_heavy = len(text_sample) > 2500
    image_ratio = analysis["image_count"] / page_count
    has_links = bool(document.has_links()) if hasattr(document, "has_links") else False
    has_annots = bool(document.has_annots()) if hasattr(document, "has_annots") else False
    is_form = bool(getattr(document, "is_form_pdf", False))
    has_signatures = document.get_sigflags() == 1 if hasattr(document, "get_sigflags") else False
    latex_like = _is_latex_like_document(text_sample, analysis["font_names"], text_heavy, image_ratio)

    if latex_like or (text_heavy and image_ratio <= 0.5):
        profile = "text"
    elif image_ratio >= 0.75 and len(text_sample) < 1500:
        profile = "image"
    else:
        profile = "mixed"

    if latex_like:
        document_type = "latex-like"
    elif text_heavy and image_ratio <= 0.5:
        document_type = "text-heavy"
    elif image_ratio >= 0.75 and len(text_sample) < 1500:
        document_type = "image-heavy"
    else:
        document_type = "mixed"

    return {
        "page_count": document.page_count,
        "image_count": analysis["image_count"],
        "text_heavy": text_heavy,
        "profile": profile,
        "document_type": document_type,
        "prefer_sharp_text": document_type in {"latex-like", "text-heavy"},
        "preserve_semantics": has_links or has_annots or is_form or has_signatures,
        "text_sample": text_sample,
    }


def _analyze_document(document: fitz.Document, sample_pages: int = 10) -> dict:
    text_sample_parts = []
    image_count = 0
    font_names = set()

    for index, page in enumerate(document):
        if index < sample_pages:
            text_sample_parts.append(page.get_text("text")[:1800])
            font_names.update(_extract_page_font_names(page))
        image_count += len(page.get_images(full=True))

    text_sample = "\n".join(part.strip() for part in text_sample_parts if part.strip())
    return {
        "image_count": image_count,
        "text_sample": text_sample,
        "font_names": sorted(font_names),
    }


def _extract_page_font_names(page: fitz.Page) -> set[str]:
    names = set()
    try:
        for entry in page.get_fonts(full=True):
            for value in entry:
                if isinstance(value, str) and any(char.isalpha() for char in value):
                    names.add(value.lower())
    except Exception:
        return names
    return names


def _is_latex_like_document(text_sample: str, font_names: list[str], text_heavy: bool, image_ratio: float) -> bool:
    if not text_heavy or image_ratio > 0.35:
        return False

    latex_font_hit = any(marker in font_name for font_name in font_names for marker in LATEX_FONT_MARKERS)
    pattern_hits = sum(len(re.findall(pattern, text_sample, flags=re.IGNORECASE)) for pattern in LATEX_TEXT_PATTERNS)
    math_symbol_hits = len(MATH_SYMBOL_PATTERN.findall(text_sample))
    equation_line_hits = sum(
        1
        for line in text_sample.splitlines()
        if len(line) >= 16 and len(EQUATION_LINE_PATTERN.findall(line)) >= 3
    )

    return latex_font_hit or (pattern_hits * 2 + equation_line_hits * 2 + math_symbol_hits >= 10)


def split_pdf(
    file_bytes: bytes,
    split_mode: str = "pages",
    ranges: list | None = None,
    sections: list | None = None,
    source_name: str = "document",
) -> list[dict]:
    document = _open_pdf(file_bytes)
    try:
        segments = _build_segments(split_mode, document.page_count, ranges or [], sections or [])
        if not segments:
            raise RequestValidationError("No valid split ranges were supplied.")

        result_files = []
        for index, segment in enumerate(segments, start=1):
            child_doc = fitz.open()
            child_doc.insert_pdf(document, from_page=segment["start"] - 1, to_page=segment["end"] - 1)
            pdf_bytes = _save_optimized_pdf(child_doc)
            child_doc.close()
            safe_label = _slugify(segment["title"]) or f"part-{index}"
            result_files.append(
                {
                    "filename": f"{source_name}-{safe_label}.pdf",
                    "bytes": pdf_bytes,
                    "size": len(pdf_bytes),
                }
            )
        return result_files
    finally:
        document.close()


def merge_pdfs(file_payloads: Iterable[bytes]) -> tuple[bytes, int]:
    merged_doc = fitz.open()
    total_pages = 0
    try:
        for payload in file_payloads:
            source_doc = _open_pdf(payload)
            try:
                merged_doc.insert_pdf(source_doc)
                total_pages += source_doc.page_count
            finally:
                source_doc.close()

        return _save_optimized_pdf(merged_doc), total_pages
    finally:
        merged_doc.close()


def pdf_to_images(
    file_bytes: bytes,
    image_format: str = "png",
    dpi: int = 160,
    quality: int = 82,
) -> list[dict]:
    normalized_format = "jpeg" if image_format in {"jpg", "jpeg"} else "png"
    mimetype = "image/jpeg" if normalized_format == "jpeg" else "image/png"
    extension = "jpg" if normalized_format == "jpeg" else "png"

    document = _open_pdf(file_bytes)
    try:
        results = []
        matrix = fitz.Matrix(dpi / 72, dpi / 72)
        for page_index, page in enumerate(document, start=1):
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            buffer = io.BytesIO()
            if normalized_format == "jpeg":
                image.save(buffer, format="JPEG", quality=quality, optimize=True)
            else:
                image.save(buffer, format="PNG", optimize=True)

            data = buffer.getvalue()
            results.append(
                {
                    "filename": f"page-{page_index}.{extension}",
                    "bytes": data,
                    "mimetype": mimetype,
                    "size": len(data),
                }
            )
        return results
    finally:
        document.close()


def images_to_pdf(image_payloads: list[tuple[bytes, str]]) -> tuple[bytes, int]:
    if not image_payloads:
        raise RequestValidationError("Upload at least one image.")

    images = []
    for payload, _filename in image_payloads:
        source_image = Image.open(io.BytesIO(payload))
        if source_image.mode in ("RGBA", "LA"):
            background = Image.new("RGB", source_image.size, "white")
            background.paste(source_image, mask=source_image.split()[-1])
            images.append(background)
        else:
            images.append(source_image.convert("RGB"))

    output = io.BytesIO()
    first_image, *rest_images = images
    first_image.save(output, format="PDF", save_all=True, append_images=rest_images)
    return output.getvalue(), len(images)


def _choose_best_compression(
    source_bytes: bytes,
    structural_bytes: bytes,
    candidates: list[dict],
    target_size_bytes: int | None,
) -> bytes:
    if not candidates:
        return structural_bytes

    best_bytes = structural_bytes
    best_under_target = structural_bytes if target_size_bytes and len(structural_bytes) <= target_size_bytes else None
    smallest_bytes = structural_bytes

    for candidate in candidates:
        try:
            candidate_bytes = _render_pdf_to_image_pdf(
                source_bytes,
                candidate["dpi"],
                candidate["quality"],
                grayscale=candidate.get("grayscale", False),
                monochrome=candidate.get("monochrome", False),
                output_format=candidate.get("format", "jpeg"),
            )
        except PdfProcessingError:
            continue

        if len(candidate_bytes) < len(smallest_bytes):
            smallest_bytes = candidate_bytes

        if target_size_bytes:
            if len(candidate_bytes) <= target_size_bytes:
                best_under_target = candidate_bytes
                break
        elif len(candidate_bytes) < len(best_bytes):
            best_bytes = candidate_bytes

    if target_size_bytes:
        return best_under_target or smallest_bytes

    return best_bytes


def _choose_best_image_recompression(
    source_bytes: bytes,
    baseline_bytes: bytes,
    candidates: list[dict],
    target_size_bytes: int | None,
) -> bytes:
    if not candidates:
        return baseline_bytes

    best_bytes = baseline_bytes
    best_under_target = baseline_bytes if target_size_bytes and len(baseline_bytes) <= target_size_bytes else None
    smallest_bytes = baseline_bytes

    for candidate in candidates:
        try:
            candidate_bytes = _recompress_embedded_images(
                source_bytes,
                max_side=candidate["max_side"],
                quality=candidate["quality"],
                grayscale=candidate["grayscale"],
            )
        except PdfProcessingError:
            continue

        if len(candidate_bytes) < len(smallest_bytes):
            smallest_bytes = candidate_bytes

        if target_size_bytes:
            if len(candidate_bytes) <= target_size_bytes:
                if best_under_target is None or len(candidate_bytes) > len(best_under_target):
                    best_under_target = candidate_bytes
        elif len(candidate_bytes) < len(best_bytes):
            best_bytes = candidate_bytes

    if target_size_bytes:
        return best_under_target or smallest_bytes

    return best_bytes


def _render_pdf_to_image_pdf(
    file_bytes: bytes,
    dpi: int,
    quality: int,
    grayscale: bool = False,
    monochrome: bool = False,
    output_format: str = "jpeg",
) -> bytes:
    source_doc = _open_pdf(file_bytes)
    target_doc = fitz.open()
    try:
        matrix = fitz.Matrix(dpi / 72, dpi / 72)
        for page in source_doc:
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            if monochrome:
                image = image.convert("L").point(lambda value: 255 if value > 180 else 0, mode="1")
            elif grayscale:
                image = image.convert("L")
            image_buffer = io.BytesIO()
            if output_format.lower() == "png":
                image.save(image_buffer, format="PNG", optimize=True)
            else:
                image.save(image_buffer, format="JPEG", quality=quality, optimize=True)

            target_page = target_doc.new_page(width=page.rect.width, height=page.rect.height)
            target_page.insert_image(target_page.rect, stream=image_buffer.getvalue())
        return _try_save_optimized_pdf(target_doc)
    finally:
        source_doc.close()
        target_doc.close()


def _recompress_embedded_images(
    file_bytes: bytes,
    max_side: int,
    quality: int,
    grayscale: bool = False,
) -> bytes:
    document = _open_pdf(file_bytes)
    seen_xrefs = {}
    try:
        for page_index, page in enumerate(document):
            for image_entry in page.get_images(full=True):
                xref = image_entry[0]
                if xref in seen_xrefs:
                    continue
                seen_xrefs[xref] = page_index

        if not seen_xrefs:
            return file_bytes

        for xref, page_index in seen_xrefs.items():
            image_info = document.extract_image(xref)
            image_bytes = image_info.get("image")
            if not image_bytes:
                continue

            image = Image.open(io.BytesIO(image_bytes))
            image.load()

            if grayscale:
                image = image.convert("L")
            elif image.mode not in ("RGB", "L"):
                if image.mode in ("RGBA", "LA"):
                    background = Image.new("RGB", image.size, "white")
                    background.paste(image, mask=image.split()[-1])
                    image = background
                else:
                    image = image.convert("RGB")

            width, height = image.size
            longest_side = max(width, height)
            if longest_side > max_side:
                scale = max_side / longest_side
                new_size = (max(1, int(width * scale)), max(1, int(height * scale)))
                image = image.resize(new_size, Image.Resampling.LANCZOS)

            buffer = io.BytesIO()
            save_format = "JPEG"
            if image.mode not in ("RGB", "L"):
                image = image.convert("RGB")
            image.save(buffer, format=save_format, quality=quality, optimize=True)

            page = document[page_index]
            page.replace_image(xref, stream=buffer.getvalue())

        return _try_save_optimized_pdf(document, fallback_bytes=file_bytes)
    except Exception as exc:
        raise PdfProcessingError("Embedded image recompression failed.") from exc
    finally:
        document.close()


def _save_optimized_pdf(document: fitz.Document) -> bytes:
    if hasattr(document, "subset_fonts"):
        try:
            document.subset_fonts(verbose=False, fallback=False)
        except Exception:
            pass

    save_variants = [
        {
            "garbage": 4,
            "clean": True,
            "deflate": True,
            "deflate_images": True,
            "deflate_fonts": True,
            "linear": True,
            "use_objstms": 1,
        },
        {
            "garbage": 4,
            "clean": True,
            "deflate": True,
            "linear": True,
        },
        {
            "garbage": 4,
            "clean": True,
            "deflate": True,
        },
    ]

    for kwargs in save_variants:
        output = io.BytesIO()
        try:
            document.save(output, **kwargs)
            return output.getvalue()
        except Exception:
            continue

    fallback_output = io.BytesIO()
    document.save(fallback_output)
    return fallback_output.getvalue()


def _try_save_optimized_pdf(document: fitz.Document, fallback_bytes: bytes | None = None) -> bytes:
    try:
        return _save_optimized_pdf(document)
    except Exception as exc:
        if fallback_bytes is not None:
            return fallback_bytes
        raise PdfProcessingError("The PDF could not be optimized safely.") from exc


def _build_segments(split_mode: str, page_count: int, ranges: list, sections: list) -> list[dict]:
    if split_mode == "sections" and sections:
        return _segments_from_sections(sections, page_count)
    if split_mode == "custom":
        return _segments_from_ranges(ranges, page_count)

    return [
        {
            "title": f"page-{page_number}",
            "start": page_number,
            "end": page_number,
        }
        for page_number in range(1, page_count + 1)
    ]


def _segments_from_ranges(ranges: list, page_count: int) -> list[dict]:
    segments = []
    for item in ranges:
        start = int(item.get("start", 0))
        end = int(item.get("end", 0))
        if start < 1 or end < start or end > page_count:
            continue
        segments.append({"title": f"pages-{start}-{end}", "start": start, "end": end})
    return segments


def _segments_from_sections(sections: list, page_count: int) -> list[dict]:
    normalized = []
    sorted_sections = sorted(
        [
            {
                "title": item.get("title", f"section-{index + 1}"),
                "start_page": max(int(item.get("start_page", 1)), 1),
                "end_page": int(item.get("end_page", 0)) if item.get("end_page") else None,
            }
            for index, item in enumerate(sections)
            if item.get("start_page")
        ],
        key=lambda item: item["start_page"],
    )

    for index, item in enumerate(sorted_sections):
        next_start = sorted_sections[index + 1]["start_page"] if index + 1 < len(sorted_sections) else page_count + 1
        end_page = item["end_page"] or (next_start - 1)
        if end_page < item["start_page"]:
            end_page = item["start_page"]

        normalized.append(
            {
                "title": item["title"],
                "start": item["start_page"],
                "end": min(end_page, page_count),
            }
        )

    return normalized


def _slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _open_pdf(file_bytes: bytes) -> fitz.Document:
    try:
        document = fitz.open(stream=file_bytes, filetype="pdf")
        if getattr(document, "needs_pass", False):
            document.close()
            raise PdfProcessingError("Password-protected PDFs are not supported yet.")
        return document
    except Exception as exc:
        if isinstance(exc, PdfProcessingError):
            raise
        raise PdfProcessingError(
            "The uploaded PDF could not be processed. It may be corrupted or use unsupported font data."
        ) from exc


def _is_target_achieved(processed_size: int, target_size_bytes: int | None) -> bool | None:
    if target_size_bytes is None:
        return None
    return processed_size <= target_size_bytes


def _should_allow_raster_fallback(
    summary: dict,
    compression_mode: str,
    compression_level: str,
    whatsapp_ready: bool,
    target_size_bytes: int | None,
    original_size: int,
) -> bool:
    if compression_mode != "fit-target" or summary["preserve_semantics"]:
        return False

    if not summary["prefer_sharp_text"]:
        return True

    if not target_size_bytes or not original_size:
        return False

    ratio = target_size_bytes / original_size
    if summary["document_type"] == "latex-like":
        return compression_level == "strong" and (ratio <= 0.35 or whatsapp_ready)

    return compression_level == "strong" and ratio <= 0.45


def _build_image_recompression_candidates(
    summary: dict,
    compression_level: str,
    whatsapp_ready: bool,
    target_size_bytes: int | None,
    original_size: int,
) -> list[dict]:
    if summary["image_count"] <= 0:
        return []

    limit = {"light": 2, "balanced": 3, "strong": 4}.get(compression_level, 3)
    if summary["profile"] == "image":
        limit += 1
    if whatsapp_ready:
        limit = max(limit, 4)
    if target_size_bytes and original_size:
        ratio = target_size_bytes / original_size
        if ratio < 0.65:
            limit += 1
        if ratio < 0.45:
            limit += 1
    return IMAGE_RECOMPRESSION_PRESETS[: min(limit, len(IMAGE_RECOMPRESSION_PRESETS))]


def _build_fit_target_candidates(
    summary: dict,
    compression_level: str,
    whatsapp_ready: bool,
    target_size_bytes: int | None,
    original_size: int,
) -> list[dict]:
    profile = summary["profile"]
    ordered = []
    seen = set()
    base_candidates = FIT_TARGET_CANDIDATES.get(profile, FIT_TARGET_CANDIDATES["mixed"])

    if profile != "text":
        for item in COMPRESSION_PRESETS.get(compression_level, COMPRESSION_PRESETS["balanced"]):
            key = (
                item["dpi"],
                item["quality"],
                item.get("grayscale", False),
                item.get("monochrome", False),
                item.get("format", "jpeg"),
            )
            if key not in seen:
                seen.add(key)
                ordered.append(item)
    if whatsapp_ready:
        for item in WHATSAPP_PRESETS:
            key = (
                item["dpi"],
                item["quality"],
                item.get("grayscale", False),
                item.get("monochrome", False),
                item.get("format", "jpeg"),
            )
            if key not in seen:
                seen.add(key)
                ordered.append(item)

    for item in base_candidates:
        key = (
            item["dpi"],
            item["quality"],
            item.get("grayscale", False),
            item.get("monochrome", False),
            item.get("format", "jpeg"),
        )
        if key not in seen:
            seen.add(key)
            ordered.append(item)

    limit = {"light": 4, "balanced": 6, "strong": 8}.get(compression_level, 6)
    if whatsapp_ready:
        limit = max(limit, 6)
    if target_size_bytes and original_size:
        ratio = target_size_bytes / original_size
        if ratio < 0.45:
            limit += 2
        if ratio < 0.3:
            limit += 2
        if ratio < 0.2:
            limit += 1

    return ordered[: min(limit, len(ordered))]


def _normalize_compression_mode(raw_mode: str | None, target_size_kb: int | None) -> str:
    normalized = str(raw_mode or "").strip().lower()
    aliases = {
        "preserve": "preserve-quality",
        "preserve-quality": "preserve-quality",
        "quality": "preserve-quality",
        "vector": "preserve-quality",
        "fit": "fit-target",
        "fit-target": "fit-target",
        "target": "fit-target",
        "hard-target": "fit-target",
    }
    if normalized in aliases:
        return aliases[normalized]
    if normalized in COMPRESSION_MODES:
        return normalized
    return "fit-target" if target_size_kb else "preserve-quality"

