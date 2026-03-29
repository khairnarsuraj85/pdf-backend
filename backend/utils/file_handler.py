from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

from flask import jsonify, send_file
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from backend.utils.errors import RequestValidationError

PDF_EXTENSIONS = {"pdf"}
IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}


def get_uploaded_file(request, field_name: str = "file", expected_kind: str = "pdf") -> FileStorage:
    uploaded_file = request.files.get(field_name)
    if not uploaded_file or not uploaded_file.filename:
        raise RequestValidationError("Please upload a file.")

    _validate_extension(uploaded_file.filename, expected_kind)
    return uploaded_file


def get_uploaded_files(request, field_name: str = "files", expected_kind: str = "pdf") -> list[FileStorage]:
    uploaded_files = request.files.getlist(field_name)
    if not uploaded_files:
        uploaded_files = request.files.getlist(f"{field_name}[]")

    valid_files = [item for item in uploaded_files if item and item.filename]
    if not valid_files:
        raise RequestValidationError("Please upload at least one file.")

    for item in valid_files:
        _validate_extension(item.filename, expected_kind)
    return valid_files


def get_uploaded_file_group(
    request,
    multi_field_name: str = "files",
    single_field_name: str = "file",
    expected_kind: str = "pdf",
) -> list[FileStorage]:
    uploaded_files = request.files.getlist(multi_field_name)
    if not uploaded_files:
        uploaded_files = request.files.getlist(f"{multi_field_name}[]")

    valid_files = [item for item in uploaded_files if item and item.filename]
    if valid_files:
        for item in valid_files:
            _validate_extension(item.filename, expected_kind)
        return valid_files

    return [get_uploaded_file(request, field_name=single_field_name, expected_kind=expected_kind)]


def read_file_bytes(uploaded_file: FileStorage) -> tuple[bytes, str]:
    filename = secure_filename(uploaded_file.filename) or "document"
    data = uploaded_file.read()
    if not data:
        raise RequestValidationError("Uploaded file is empty.")
    return data, filename


def filename_stem(filename: str) -> str:
    return filename.rsplit(".", 1)[0]


def stream_bytes(filename: str, data: bytes, mimetype: str):
    return send_file(
        io.BytesIO(data),
        as_attachment=True,
        download_name=filename,
        mimetype=mimetype,
        max_age=0,
    )


def zip_named_files(named_files: list[dict]) -> bytes:
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zip_stream:
        for item in named_files:
            zip_stream.writestr(item["filename"], item["bytes"])
    return archive.getvalue()


def parse_bool(raw_value) -> bool:
    return str(raw_value).strip().lower() in {"1", "true", "yes", "on"}


def parse_int(
    raw_value,
    fallback: int | None = None,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int | None:
    if raw_value in (None, ""):
        return fallback
    try:
        value = int(raw_value)
    except (TypeError, ValueError) as exc:
        raise RequestValidationError("Invalid numeric value supplied.") from exc
    if minimum is not None and value < minimum:
        raise RequestValidationError(f"Numeric value must be at least {minimum}.")
    if maximum is not None and value > maximum:
        raise RequestValidationError(f"Numeric value must be at most {maximum}.")
    return value


def parse_json_field(raw_value, default=None):
    if raw_value in (None, ""):
        return default
    try:
        return json.loads(raw_value)
    except (TypeError, ValueError) as exc:
        raise RequestValidationError("Invalid JSON payload supplied.") from exc


def attach_processing_headers(
    response,
    tool: str,
    original_size: int,
    processed_size: int,
    page_count: int | None = None,
    output_count: int | None = None,
):
    response.headers["X-Tool"] = tool
    response.headers["X-Original-Size"] = str(original_size)
    response.headers["X-Processed-Size"] = str(processed_size)
    if page_count is not None:
        response.headers["X-Page-Count"] = str(page_count)
    if output_count is not None:
        response.headers["X-Output-Count"] = str(output_count)


def error_response(message: str, status_code: int = 400):
    return jsonify({"error": message}), status_code


def _validate_extension(filename: str, expected_kind: str):
    extension = Path(filename).suffix.lower().lstrip(".")
    valid_extensions = PDF_EXTENSIONS if expected_kind == "pdf" else IMAGE_EXTENSIONS
    if extension not in valid_extensions:
        expected_label = "PDF" if expected_kind == "pdf" else "image"
        raise RequestValidationError(f"Unsupported file type. Please upload a valid {expected_label} file.")
