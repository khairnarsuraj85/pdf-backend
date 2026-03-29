from flask import Blueprint, request

from backend.routes.common import handle_route_errors
from backend.services.pdf_service import merge_pdfs
from backend.utils.file_handler import (
    attach_processing_headers,
    get_uploaded_files,
    read_file_bytes,
    stream_bytes,
)

merge_bp = Blueprint("merge", __name__)


@merge_bp.post("/merge")
@handle_route_errors("Merge failed.")
def merge_route():
    uploaded_files = get_uploaded_files(request, field_name="files", expected_kind="pdf")
    file_payloads = [read_file_bytes(item) for item in uploaded_files]
    merged_bytes, page_count = merge_pdfs([payload[0] for payload in file_payloads])

    response = stream_bytes("merged-document.pdf", merged_bytes, "application/pdf")
    attach_processing_headers(
        response,
        tool="merge",
        original_size=sum(len(payload[0]) for payload in file_payloads),
        processed_size=len(merged_bytes),
        page_count=page_count,
        output_count=1,
    )
    return response
