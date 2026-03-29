from __future__ import annotations

import json
import os
import re

from dotenv import load_dotenv

load_dotenv()


def suggest_compression(file_info: dict) -> dict:
    prompt = _build_compression_prompt(file_info)

    openai_result = _try_openai(prompt)
    if openai_result:
        return {"provider": "openai", "recommendation": openai_result}

    gemini_result = _try_gemini(prompt)
    if gemini_result:
        return {"provider": "gemini", "recommendation": gemini_result}

    return {"provider": "rule-based", "recommendation": _rule_based_compression(file_info)}


def detect_sections(page_map: list[dict]) -> dict:
    candidate_pages = _condense_page_map_for_sections(page_map)
    if not candidate_pages:
        sections = _rule_based_sections(page_map)
        return {
            "provider": "rule-based",
            "sections": sections,
            "confidence": "medium" if sections else "low",
        }

    prompt = _build_section_prompt(candidate_pages)

    openai_result = _try_openai(prompt)
    if openai_result:
        return {
            "provider": "openai",
            "sections": openai_result.get("sections", []),
            "confidence": openai_result.get("confidence", "high"),
        }

    gemini_result = _try_gemini(prompt)
    if gemini_result:
        return {
            "provider": "gemini",
            "sections": gemini_result.get("sections", []),
            "confidence": gemini_result.get("confidence", "medium"),
        }

    sections = _rule_based_sections(page_map)
    return {
        "provider": "rule-based",
        "sections": sections,
        "confidence": "medium" if sections else "low",
    }


def _try_openai(prompt: str) -> dict | None:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None

    try:
        return _run_openai_prompt(api_key, prompt)
    except Exception:
        return None


def _try_gemini(prompt: str) -> dict | None:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None

    try:
        return _run_gemini_prompt(api_key, prompt)
    except Exception:
        return None


def _safe_json_parse(content: str) -> dict:
    normalized = content.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(normalized)


def _run_openai_prompt(api_key: str, prompt: str) -> dict:
    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        temperature=0.2,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a PDF workflow assistant. Always reply with valid JSON only. "
                    "Do not wrap the JSON in markdown."
                ),
            },
            {"role": "user", "content": prompt},
        ],
    )
    content = response.choices[0].message.content or "{}"
    return _safe_json_parse(content)


def _run_gemini_prompt(api_key: str, prompt: str) -> dict:
    import google.generativeai as genai

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(os.getenv("GEMINI_MODEL", "gemini-1.5-flash"))
    response = model.generate_content(prompt)
    content = getattr(response, "text", "") or "{}"
    return _safe_json_parse(content)


def _build_compression_prompt(file_info: dict) -> str:
    return (
        "Analyze this PDF and recommend the best compression profile.\n"
        "Return JSON with keys: mode, level, targetSizeKB, whatsappReady, reasoning, CTA.\n"
        "Valid modes: preserve-quality, fit-target.\n"
        "Valid levels: light, balanced, strong.\n"
        f"PDF info: {json.dumps(file_info, ensure_ascii=True)}"
    )


def _build_section_prompt(page_map: list[dict]) -> str:
    return (
        "Detect major split points in this PDF.\n"
        "Return JSON with keys: sections, confidence.\n"
        "sections must be an array of objects with title and start_page.\n"
        "Use only headings that look like real document sections.\n"
        "The input already contains only condensed heading candidates, not full pages.\n"
        f"Page content: {json.dumps(page_map, ensure_ascii=True)}"
    )


def _condense_page_map_for_sections(page_map: list[dict], max_chars: int = 12000) -> list[dict]:
    condensed = []
    total_chars = 0

    for page in page_map:
        lines = [line.strip() for line in str(page.get("text", "")).splitlines() if line.strip()]
        headings = []
        for line in lines[:8]:
            normalized = line[:120]
            if _looks_like_heading(normalized):
                headings.append(normalized)
        if not headings:
            continue

        payload = {"page": page["page"], "headings": headings[:3]}
        serialized = json.dumps(payload, ensure_ascii=True)
        if total_chars + len(serialized) > max_chars:
            break
        condensed.append(payload)
        total_chars += len(serialized)

    if condensed:
        return condensed

    fallback = []
    for page in page_map[:12]:
        snippet = str(page.get("text", "")).strip()
        if not snippet:
            continue
        payload = {"page": page["page"], "headings": [snippet[:120]]}
        serialized = json.dumps(payload, ensure_ascii=True)
        if total_chars + len(serialized) > max_chars:
            break
        fallback.append(payload)
        total_chars += len(serialized)

    return fallback


def _looks_like_heading(line: str) -> bool:
    lowered = line.lower()
    if lowered.startswith(("chapter", "section", "part", "unit", "module", "appendix")):
        return True
    if re.match(r"^\d+(\.\d+)*\s+\S+", line):
        return True
    return len(line) <= 90 and line == line.upper() and any(char.isalpha() for char in line)


def _rule_based_compression(file_info: dict) -> dict:
    size_kb = file_info.get("sizeKB", 0)
    page_count = file_info.get("pageCount", 1)
    has_images = file_info.get("hasImages", False)
    text_density = file_info.get("textDensity", "mixed")
    document_type = file_info.get("documentType", "mixed")
    prefer_sharp_text = bool(file_info.get("preferSharpText"))

    if document_type == "latex-like":
        mode = "preserve-quality"
        level = "light"
        target_size_kb = 500 if page_count > 8 else 200
    elif size_kb > 3500 or has_images:
        mode = "fit-target"
        level = "strong"
        target_size_kb = 500 if page_count > 10 else 200
    elif text_density == "text-heavy":
        mode = "preserve-quality"
        level = "light"
        target_size_kb = 200 if page_count <= 10 else 500
    else:
        mode = "fit-target"
        level = "balanced"
        target_size_kb = 500

    whatsapp_ready = size_kb > 800
    return {
        "mode": mode,
        "level": level,
        "targetSizeKB": target_size_kb,
        "whatsappReady": whatsapp_ready,
        "reasoning": (
            "Rule-based fallback selected a profile using file size, page count, image density, text density, and whether the PDF looks like a LaTeX or text-heavy document."
        ),
        "CTA": (
            "This looks like a text-first document, so preserve-quality mode is safer for sharp output."
            if prefer_sharp_text
            else "Use the suggested profile for the fastest result, or switch to target compression for tighter size limits."
        ),
    }


def _rule_based_sections(page_map: list[dict]) -> list[dict]:
    sections = []
    for page in page_map:
        lines = [line.strip() for line in page.get("text", "").splitlines() if line.strip()]
        for line in lines[:6]:
            lowered = line.lower()
            if lowered.startswith(("chapter", "section", "part", "unit", "module")):
                sections.append({"title": line[:80], "start_page": page["page"]})
                break

    deduped = []
    seen_pages = set()
    for item in sections:
        if item["start_page"] in seen_pages:
            continue
        seen_pages.add(item["start_page"])
        deduped.append(item)
    return deduped
