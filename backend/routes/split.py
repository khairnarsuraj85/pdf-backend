from flask import Blueprint, request

from backend.routes.common import handle_route_errors
from backend.services.pdf_service import split_pdf
from backend.utils.file_handler import (
    attach_processing_headers,
    filename_stem,
    get_uploaded_file,
    parse_json_field,
    read_file_bytes,
    stream_bytes,
    zip_named_files,
)

split_bp = Blueprint("split", __name__)


@split_bp.post("/split")
@handle_route_errors("Split failed.")
def split_route():
    uploaded_file = get_uploaded_file(request, field_name="file", expected_kind="pdf")
    file_bytes, filename = read_file_bytes(uploaded_file)
    split_mode = request.form.get("splitMode", "pages").strip().lower()
    ranges = parse_json_field(request.form.get("ranges"), default=[])
    sections = parse_json_field(request.form.get("sections"), default=[])

    result_files = split_pdf(
        file_bytes,
        split_mode=split_mode,
        ranges=ranges,
        sections=sections,
        source_name=filename_stem(filename),
    )

    if len(result_files) == 1:
        only_file = result_files[0]
        response = stream_bytes(only_file["filename"], only_file["bytes"], "application/pdf")
        processed_size = only_file["size"]
    else:
        archive_bytes = zip_named_files(result_files)
        response = stream_bytes(
            f"{filename_stem(filename)}-split.zip",
            archive_bytes,
            "application/zip",
        )
        processed_size = len(archive_bytes)

    attach_processing_headers(
        response,
        tool="split",
        original_size=len(file_bytes),
        processed_size=processed_size,
        output_count=len(result_files),
    )
    return response
