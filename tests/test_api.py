import io
import json
import os
import unittest
import zipfile
from unittest.mock import patch

import fitz
from PIL import Image, ImageDraw

from app import app


def make_text_pdf(pages=3, heading_prefix="Section"):
    document = fitz.open()
    try:
        for index in range(pages):
            page = document.new_page()
            title = f"{heading_prefix} {index + 1}"
            body = "This is a backend API regression test. " * 120
            page.insert_textbox(fitz.Rect(40, 40, 560, 760), f"{title}\n{body}", fontsize=12)
        return _save_doc(document)
    finally:
        document.close()


def make_heading_pdf():
    document = fitz.open()
    try:
        for index in range(3):
            page = document.new_page()
            page.insert_text((40, 60), f"Chapter {index + 1}", fontsize=18)
            page.insert_textbox(
                fitz.Rect(40, 100, 560, 760),
                "This page contains chapter content for smart split testing. " * 80,
                fontsize=12,
            )
        return _save_doc(document)
    finally:
        document.close()


def make_latex_like_pdf(pages=2):
    document = fitz.open()
    try:
        body = (
            "Theorem 1.1 Let f(x) = x^2 + y^2. "
            "Proof. By Equation (1), \\sum_{i=1}^n a_i = \\lambda^2 and \\int_0^1 x dx = 1/2. "
            "Lemma 2.1 This academic text is formula heavy and keeps sharp text important. "
        )
        for _index in range(pages):
            page = document.new_page()
            page.insert_textbox(fitz.Rect(40, 40, 560, 760), body * 20, fontsize=12)
        return _save_doc(document)
    finally:
        document.close()


def make_link_pdf():
    document = fitz.open()
    try:
        page = document.new_page()
        page.insert_text((72, 72), "OpenAI docs", fontsize=14)
        page.insert_link(
            {
                "kind": fitz.LINK_URI,
                "from": fitz.Rect(70, 55, 180, 80),
                "uri": "https://platform.openai.com/docs",
            }
        )
        return _save_doc(document)
    finally:
        document.close()


def make_password_pdf():
    document = fitz.open()
    try:
        page = document.new_page()
        page.insert_text((72, 72), "Secret")
        output = io.BytesIO()
        document.save(
            output,
            encryption=fitz.PDF_ENCRYPT_AES_256,
            owner_pw="owner",
            user_pw="user",
        )
        return output.getvalue()
    finally:
        document.close()


def make_image_bytes(label):
    image = Image.new("RGB", (1200, 800), (255, 248, 240))
    draw = ImageDraw.Draw(image)
    draw.rectangle((30, 30, 1170, 770), outline=(20, 70, 180), width=8)
    draw.text((60, 60), label, fill=(0, 0, 0))
    output = io.BytesIO()
    image.save(output, format="JPEG", quality=88)
    return output.getvalue()


def _save_doc(document):
    output = io.BytesIO()
    document.save(output)
    return output.getvalue()


class ApiTestCase(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_compress_preserves_semantic_pdf(self):
        response = self.client.post(
            "/compress",
            data={
                "file": (io.BytesIO(make_link_pdf()), "link.pdf"),
                "compressionMode": "fit-target",
                "compressionLevel": "balanced",
                "targetSizeKB": "1",
                "whatsappReady": "false",
            },
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("X-Compression-Strategy"), "vector-safe")

    def test_compress_flags_latex_like_pdf_for_text_priority(self):
        response = self.client.post(
            "/compress",
            data={
                "file": (io.BytesIO(make_latex_like_pdf()), "latex-like.pdf"),
                "compressionMode": "fit-target",
                "compressionLevel": "balanced",
                "targetSizeKB": "1",
                "whatsappReady": "false",
            },
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("X-Document-Type"), "latex-like")
        self.assertEqual(response.headers.get("X-Text-Priority"), "true")
        self.assertEqual(response.headers.get("X-Compression-Strategy"), "vector-safe")

    def test_compress_batch_returns_zip_archive(self):
        response = self.client.post(
            "/compress",
            data={
                "files": [
                    (io.BytesIO(make_text_pdf(pages=1, heading_prefix="Batch")), "first.pdf"),
                    (io.BytesIO(make_text_pdf(pages=1, heading_prefix="Batch")), "second.pdf"),
                ],
                "compressionMode": "fit-target",
                "compressionLevel": "balanced",
                "targetSizeKB": "200",
                "whatsappReady": "false",
            },
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "application/zip")
        self.assertEqual(response.headers.get("X-Batch-Compression"), "true")
        self.assertEqual(response.headers.get("X-Output-Count"), "2")
        self.assertEqual(int(response.headers["X-Processed-Size"]), len(response.data))

        archive = zipfile.ZipFile(io.BytesIO(response.data))
        self.assertEqual(sorted(archive.namelist()), ["first-compressed.pdf", "second-compressed.pdf"])

    def test_compress_rejects_password_protected_pdf(self):
        response = self.client.post(
            "/compress",
            data={
                "file": (io.BytesIO(make_password_pdf()), "protected.pdf"),
                "compressionMode": "fit-target",
                "compressionLevel": "balanced",
                "targetSizeKB": "200",
                "whatsappReady": "false",
            },
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 422)
        payload = response.get_json()
        self.assertIn("Password-protected", payload["error"])

    def test_split_zip_reports_actual_archive_size(self):
        response = self.client.post(
            "/split",
            data={
                "file": (io.BytesIO(make_text_pdf(pages=3)), "sample.pdf"),
                "splitMode": "custom",
                "ranges": json.dumps([{"start": 1, "end": 1}, {"start": 2, "end": 3}]),
            },
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "application/zip")
        self.assertEqual(int(response.headers["X-Processed-Size"]), len(response.data))

    def test_pdf_to_image_rejects_out_of_range_dpi(self):
        response = self.client.post(
            "/pdf-to-image",
            data={
                "file": (io.BytesIO(make_text_pdf(pages=1)), "sample.pdf"),
                "format": "jpg",
                "dpi": "9999",
                "quality": "82",
            },
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("at most 240", response.get_json()["error"])

    def test_ai_suggest_falls_back_without_provider_keys(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "", "GEMINI_API_KEY": ""}, clear=False):
            response = self.client.post(
                "/ai/suggest-compression",
                data={"file": (io.BytesIO(make_text_pdf(pages=2)), "sample.pdf")},
                content_type="multipart/form-data",
            )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["provider"], "rule-based")

    def test_ai_smart_split_detects_headings(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "", "GEMINI_API_KEY": ""}, clear=False):
            response = self.client.post(
                "/ai/smart-split",
                data={"file": (io.BytesIO(make_heading_pdf()), "sample.pdf")},
                content_type="multipart/form-data",
            )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertGreaterEqual(len(payload["sections"]), 1)


if __name__ == "__main__":
    unittest.main()
