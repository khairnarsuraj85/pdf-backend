from flask import Blueprint, request

from backend.routes.common import handle_route_errors
from backend.services.pdf_service import compress_pdf
from backend.utils.file_handler import (
    attach_processing_headers,
    filename_stem,
    get_uploaded_file_group,
    parse_bool,
    parse_int,
    read_file_bytes,
    stream_bytes,
    zip_named_files,
)

compress_bp = Blueprint("compress", __name__)


@compress_bp.post("/compress")
@handle_route_errors("Compression failed.")
def compress_route():
    uploaded_files = get_uploaded_file_group(request, multi_field_name="files", single_field_name="file", expected_kind="pdf")
    file_payloads = [read_file_bytes(item) for item in uploaded_files]
    target_size_kb = parse_int(request.form.get("targetSizeKB"), minimum=1, maximum=102400)
    compression_level = request.form.get("compressionLevel", "balanced").strip().lower()
    compression_mode = request.form.get("compressionMode")
    whatsapp_ready = parse_bool(request.form.get("whatsappReady"))

    results = [
        compress_pdf(
            file_bytes,
            compression_level,
            target_size_kb,
            whatsapp_ready,
            compression_mode,
        )
        for file_bytes, _filename in file_payloads
    ]

    if len(file_payloads) == 1:
        filename = file_payloads[0][1]
        result = results[0]
        response = stream_bytes(f"{filename_stem(filename)}-compressed.pdf", result["bytes"], "application/pdf")
        processed_size = result["processed_size"]
        page_count = result["page_count"]
        strategy = result["strategy"]
        profile = result["profile"]
        document_type = result["document_type"]
        text_priority = result["text_priority"]
    else:
        named_files = [
            {
                "filename": f"{filename_stem(filename)}-compressed.pdf",
                "bytes": result["bytes"],
            }
            for (_file_bytes, filename), result in zip(file_payloads, results, strict=False)
        ]
        archive_bytes = zip_named_files(named_files)
        response = stream_bytes("compressed-pdfs.zip", archive_bytes, "application/zip")
        processed_size = len(archive_bytes)
        page_count = sum(item["page_count"] for item in results)
        strategies = {item["strategy"] for item in results}
        profiles = {item["profile"] for item in results}
        document_types = {item["document_type"] for item in results}
        text_priorities = {item["text_priority"] for item in results}
        strategy = strategies.pop() if len(strategies) == 1 else "mixed"
        profile = profiles.pop() if len(profiles) == 1 else "batch"
        document_type = document_types.pop() if len(document_types) == 1 else "mixed-batch"
        text_priority = len(text_priorities) == 1 and text_priorities.pop()

    total_original_size = sum(len(file_bytes) for file_bytes, _filename in file_payloads)
    target_achieved_values = [item["target_achieved"] for item in results if item["target_achieved"] is not None]
    aggregate_target_achieved = all(target_achieved_values) if target_achieved_values else None
    aggregate_ratio = 1 - (processed_size / total_original_size if total_original_size else 1)
    attach_processing_headers(
        response,
        tool="compress",
        original_size=total_original_size,
        processed_size=processed_size,
        page_count=page_count,
        output_count=len(file_payloads) if len(file_payloads) > 1 else None,
    )
    response.headers["X-Compression-Ratio"] = f"{max(aggregate_ratio, 0):.2f}"
    response.headers["X-Compression-Mode"] = compression_mode or results[0]["mode"]
    response.headers["X-Compression-Strategy"] = strategy
    response.headers["X-Compression-Profile"] = profile
    response.headers["X-Document-Type"] = document_type
    response.headers["X-Text-Priority"] = str(text_priority).lower()
    response.headers["X-Batch-Compression"] = str(len(file_payloads) > 1).lower()
    if target_size_kb is not None:
        response.headers["X-Requested-Target-KB"] = str(target_size_kb)
    if aggregate_target_achieved is not None:
        response.headers["X-Target-Achieved"] = str(aggregate_target_achieved).lower()
    return response
