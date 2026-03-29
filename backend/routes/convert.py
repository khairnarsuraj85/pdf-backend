from flask import Blueprint, request

from backend.routes.common import handle_route_errors
from backend.services.pdf_service import images_to_pdf, pdf_to_images
from backend.utils.errors import RequestValidationError
from backend.utils.file_handler import (
    attach_processing_headers,
    filename_stem,
    get_uploaded_file,
    get_uploaded_files,
    parse_int,
    read_file_bytes,
    stream_bytes,
    zip_named_files,
)

convert_bp = Blueprint("convert", __name__)


@convert_bp.post("/pdf-to-image")
@handle_route_errors("PDF to image conversion failed.")
def pdf_to_image_route():
    uploaded_file = get_uploaded_file(request, field_name="file", expected_kind="pdf")
    file_bytes, filename = read_file_bytes(uploaded_file)
    image_format = request.form.get("format", "png").strip().lower()
    if image_format not in {"png", "jpg", "jpeg"}:
        raise RequestValidationError("Unsupported image format. Choose PNG or JPG.")
    dpi = parse_int(request.form.get("dpi"), fallback=160, minimum=72, maximum=240) or 160
    quality = parse_int(request.form.get("quality"), fallback=82, minimum=40, maximum=95) or 82

    result_files = pdf_to_images(file_bytes, image_format, dpi, quality)

    if len(result_files) == 1:
        only_file = result_files[0]
        response = stream_bytes(only_file["filename"], only_file["bytes"], only_file["mimetype"])
        processed_size = only_file["size"]
    else:
        archive_bytes = zip_named_files(result_files)
        response = stream_bytes(
            f"{filename_stem(filename)}-images.zip",
            archive_bytes,
            "application/zip",
        )
        processed_size = len(archive_bytes)

    attach_processing_headers(
        response,
        tool="pdf-to-image",
        original_size=len(file_bytes),
        processed_size=processed_size,
        output_count=len(result_files),
    )
    return response


@convert_bp.post("/image-to-pdf")
@handle_route_errors("Image to PDF conversion failed.")
def image_to_pdf_route():
    uploaded_files = get_uploaded_files(request, field_name="files", expected_kind="image")
    file_payloads = [read_file_bytes(item) for item in uploaded_files]
    pdf_bytes, page_count = images_to_pdf(file_payloads)

    response = stream_bytes("converted-images.pdf", pdf_bytes, "application/pdf")
    attach_processing_headers(
        response,
        tool="image-to-pdf",
        original_size=sum(len(payload[0]) for payload in file_payloads),
        processed_size=len(pdf_bytes),
        page_count=page_count,
        output_count=1,
    )
    return response
