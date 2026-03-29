from flask import Blueprint, jsonify, request

from backend.routes.common import handle_route_errors
from backend.services.ai_service import detect_sections, suggest_compression
from backend.services.pdf_service import extract_page_map, inspect_pdf
from backend.utils.file_handler import get_uploaded_file, read_file_bytes

ai_bp = Blueprint("ai", __name__, url_prefix="/ai")


@ai_bp.post("/suggest-compression")
@handle_route_errors("AI suggestion failed.")
def suggest_compression_route():
    uploaded_file = get_uploaded_file(request, field_name="file", expected_kind="pdf")
    file_bytes, filename = read_file_bytes(uploaded_file)
    file_info = inspect_pdf(file_bytes)
    file_info["filename"] = filename

    suggestion = suggest_compression(file_info)
    return jsonify(
        {
            "provider": suggestion["provider"],
            "recommendation": suggestion["recommendation"],
            "fileInfo": file_info,
        }
    )


@ai_bp.post("/smart-split")
@handle_route_errors("Smart split failed.")
def smart_split_route():
    uploaded_file = get_uploaded_file(request, field_name="file", expected_kind="pdf")
    file_bytes, _filename = read_file_bytes(uploaded_file)
    page_map = extract_page_map(file_bytes)
    result = detect_sections(page_map)
    return jsonify(result)
