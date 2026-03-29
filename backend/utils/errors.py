class RequestValidationError(Exception):
    """Raised for client-side validation problems in request payloads."""


class PdfProcessingError(Exception):
    """Raised when a PDF cannot be processed reliably."""

