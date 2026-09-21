"""Bounded, literal document extraction; this module never interprets clinical facts.

Locations are one based. DOCX paragraphs/tables retain body order; nested table
content is extracted recursively. OCR is opt in and never silently reported as
successful when disabled, unavailable, timed out, or unable to recognize text.
"""

from __future__ import annotations

import io
from pathlib import PurePosixPath
from typing import Literal
import unicodedata
import warnings
import zipfile
from xml.etree import ElementTree

from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, Field

from app.utils.document_errors import DocumentError


MAX_INPUT_BYTES = 20 * 1024 * 1024
MAX_DOCX_UNCOMPRESSED_BYTES = 50 * 1024 * 1024
MAX_DOCX_MEMBERS = 2000
MIME_TYPES = {
    ".txt": "text/plain",
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
}


class ExtractedChunk(BaseModel):
    text: str
    location: dict[str, int | str]
    method: Literal["text", "ocr"]


class ExtractionResult(BaseModel):
    status: Literal["processed", "partial", "ocr_required"]
    chunks: list[ExtractedChunk] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


def _error(code: str, message: str) -> DocumentError:
    return DocumentError(code, message)


def _check_docx_archive(data: bytes) -> None:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            members = archive.infolist()
            if len(members) > MAX_DOCX_MEMBERS:
                raise _error("DOCUMENT_LIMIT_EXCEEDED", "DOCX contains too many ZIP entries.")
            if sum(item.file_size for item in members) > MAX_DOCX_UNCOMPRESSED_BYTES:
                raise _error("DOCUMENT_LIMIT_EXCEEDED", "DOCX expanded size exceeds the limit.")
            names: set[str] = set()
            for item in members:
                path = PurePosixPath(item.filename)
                if (
                    item.flag_bits & 1
                    or path.is_absolute()
                    or ".." in path.parts
                    or "\\" in item.filename
                    or ":" in item.filename
                    or any(unicodedata.category(char).startswith("C") for char in item.filename)
                    or item.filename in names
                ):
                    raise _error("DOCUMENT_PARSE_FAILED", "DOCX contains an unsafe ZIP entry.")
                names.add(item.filename)
            if not {"[Content_Types].xml", "word/document.xml", "_rels/.rels"}.issubset(names):
                raise _error("DOCUMENT_PARSE_FAILED", "File is not a valid DOCX package.")
            content_types = ElementTree.fromstring(archive.read("[Content_Types].xml"))
            valid_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"
            if not any(
                item.get("PartName") == "/word/document.xml" and item.get("ContentType") == valid_type
                for item in content_types
            ):
                raise _error("UNSUPPORTED_FILE_TYPE", "Only non-macro DOCX documents are supported.")
    except DocumentError:
        raise
    except (zipfile.BadZipFile, KeyError, ValueError, RuntimeError, ElementTree.ParseError) as exc:
        raise _error("DOCUMENT_PARSE_FAILED", "DOCX package could not be read.") from exc


def _read_image(data: bytes, max_image_pixels: int) -> Image.Image:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            image = Image.open(io.BytesIO(data))
            try:
                if image.width * image.height > max_image_pixels:
                    raise _error("DOCUMENT_LIMIT_EXCEEDED", "Image pixel count exceeds the limit.")
                if image.format not in {"PNG", "JPEG"}:
                    raise _error("UNSUPPORTED_FILE_TYPE", "Only PNG and JPEG images are supported.")
                image.verify()
            finally:
                image.close()
            image = Image.open(io.BytesIO(data))
            try:
                image.load()
                return image.convert("RGB")
            finally:
                image.close()
    except DocumentError:
        raise
    except (Image.DecompressionBombWarning, Image.DecompressionBombError) as exc:
        raise _error("DOCUMENT_LIMIT_EXCEEDED", "Image dimensions exceed the safe limit.") from exc
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise _error("DOCUMENT_PARSE_FAILED", "Image could not be decoded.") from exc


def validate_file(
    filename: str, data: bytes, content_type: str | None, max_bytes: int
) -> tuple[str, str]:
    """Validate filename, MIME and actual content before storage or extraction."""
    if (
        not filename
        or filename != filename.strip()
        or len(filename.encode("utf-8")) > 255
        or filename in {".", ".."}
        or any(char in filename for char in "/\\:")
        or any(unicodedata.category(char).startswith("C") for char in filename)
    ):
        raise _error("INVALID_FILENAME", "Use a filename without directories or control characters.")
    extension = PurePosixPath(filename).suffix.lower()
    if extension not in MIME_TYPES:
        raise _error("UNSUPPORTED_FILE_TYPE", "Supported files are TXT, PDF, DOCX, PNG and JPEG; legacy DOC is unsupported.")
    if not data:
        raise _error("EMPTY_FILE", "The uploaded file is empty.")
    if max_bytes <= 0 or len(data) > min(max_bytes, MAX_INPUT_BYTES):
        raise DocumentError("FILE_TOO_LARGE", "The uploaded file exceeds the size limit.", status_code=413)
    expected = MIME_TYPES[extension]
    provided = (content_type or "").split(";", 1)[0].strip().lower()
    if provided and provided not in {expected, "application/octet-stream"}:
        raise _error("UNSUPPORTED_FILE_TYPE", "The content type does not match the filename.")
    if extension == ".txt":
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise _error("DOCUMENT_PARSE_FAILED", "TXT files must use UTF-8 encoding.") from exc
        if any(unicodedata.category(char) == "Cc" and char not in "\n\r\t\f" for char in text):
            raise _error("DOCUMENT_PARSE_FAILED", "TXT file contains binary control characters.")
    elif extension == ".pdf":
        if not data.startswith(b"%PDF-"):
            raise _error("UNSUPPORTED_FILE_TYPE", "File content is not a PDF.")
    elif extension == ".docx":
        if not data.startswith(b"PK\x03\x04"):
            raise _error("UNSUPPORTED_FILE_TYPE", "File content is not a DOCX.")
        _check_docx_archive(data)
    elif extension == ".png":
        if not data.startswith(b"\x89PNG\r\n\x1a\n"):
            raise _error("UNSUPPORTED_FILE_TYPE", "File content is not a PNG image.")
    elif not data.startswith(b"\xff\xd8\xff"):
        raise _error("UNSUPPORTED_FILE_TYPE", "File content is not a JPEG image.")
    return filename, expected


def _ocr_image(image: Image.Image, language: str, timeout: int) -> str:
    try:
        import pytesseract
    except ImportError as exc:
        raise _error("OCR_UNAVAILABLE", "Install the OCR dependencies and Tesseract to enable OCR.") from exc
    try:
        return pytesseract.image_to_string(image, lang=language, timeout=timeout).strip()
    except pytesseract.TesseractNotFoundError as exc:
        raise _error("OCR_UNAVAILABLE", "The Tesseract executable is unavailable.") from exc
    except pytesseract.TesseractError as exc:
        raise _error("OCR_UNAVAILABLE", "Tesseract failed; check the installed OCR language data.") from exc
    except RuntimeError as exc:
        raise _error("OCR_TIMEOUT", "OCR exceeded its processing time limit.") from exc


def _ocr_pdf_page(data: bytes, index: int, language: str, timeout: int, max_pixels: int) -> str:
    try:
        import pypdfium2 as pdfium
    except ImportError as exc:
        raise _error("OCR_UNAVAILABLE", "Install pypdfium2 to OCR scanned PDFs.") from exc
    try:
        with pdfium.PdfDocument(data) as document:
            page = document[index]
            try:
                width, height = page.get_size()
                if width * height * 4 > max_pixels:
                    raise _error("DOCUMENT_LIMIT_EXCEEDED", "Rendered PDF page exceeds the image pixel limit.")
                bitmap = page.render(scale=2)
                try:
                    image = bitmap.to_pil()
                    try:
                        return _ocr_image(image, language, timeout)
                    finally:
                        image.close()
                finally:
                    bitmap.close()
            finally:
                page.close()
    except DocumentError:
        raise
    except Exception as exc:
        raise _error("DOCUMENT_PARSE_FAILED", "PDF page could not be rendered for OCR.") from exc


def extract_document(
    filename: str,
    data: bytes,
    *,
    ocr_enabled: bool = False,
    ocr_language: str = "eng",
    max_pdf_pages: int = 50,
    max_text_chars: int = 200000,
    max_image_pixels: int = 20000000,
    ocr_timeout_seconds: int = 20,
) -> ExtractionResult:
    """Return literal source text and locations; never update session state."""
    validate_file(filename, data, None, MAX_INPUT_BYTES)
    if min(max_pdf_pages, max_text_chars, max_image_pixels, ocr_timeout_seconds) <= 0:
        raise _error("DOCUMENT_LIMIT_EXCEEDED", "Document processing limits must be positive.")
    extension = PurePosixPath(filename).suffix.lower()
    chunks: list[ExtractedChunk] = []
    messages: list[str] = []
    total_chars = 0
    missing_text = False

    def append(text: str, location: dict[str, int | str], method: Literal["text", "ocr"] = "text") -> None:
        nonlocal total_chars
        total_chars += len(text)
        if total_chars > max_text_chars:
            raise _error("DOCUMENT_LIMIT_EXCEEDED", "Extracted text exceeds the character limit.")
        if text.strip():
            chunks.append(ExtractedChunk(text=text, location=location, method=method))

    def perform_ocr(location: dict[str, int | str], action) -> None:
        nonlocal missing_text
        label = ", ".join(f"{key} {value}" for key, value in location.items())
        if not ocr_enabled:
            missing_text = True
            messages.append(f"OCR_DISABLED: {label} requires OCR; no text extracted.")
            return
        try:
            text = action()
        except DocumentError as exc:
            if exc.code not in {"OCR_UNAVAILABLE", "OCR_TIMEOUT"}:
                raise
            missing_text = True
            messages.append(f"{exc.code}: {label}: {exc.message}")
            return
        if not text.strip():
            missing_text = True
            messages.append(f"OCR_NO_TEXT: {label} produced no recognized text; review the source manually.")
            return
        append(text, location, "ocr")
        messages.append(f"OCR_REVIEW_REQUIRED: {label} contains machine-recognized text; verify against the source.")

    try:
        if extension == ".txt":
            text = data.decode("utf-8-sig")
            if len(text) > max_text_chars:
                raise _error("DOCUMENT_LIMIT_EXCEEDED", "Text exceeds the character limit.")
            for index, line in enumerate(text.splitlines(), 1):
                append(line, {"line": index})
        elif extension == ".pdf":
            from pypdf import PdfReader

            reader = PdfReader(io.BytesIO(data))
            if reader.is_encrypted:
                raise _error("DOCUMENT_PARSE_FAILED", "Encrypted PDFs are unsupported; upload an unencrypted copy.")
            if len(reader.pages) > max_pdf_pages:
                raise _error("DOCUMENT_LIMIT_EXCEEDED", "PDF page count exceeds the limit.")
            for index, page in enumerate(reader.pages):
                text = page.extract_text() or ""
                if text.strip():
                    append(text, {"page": index + 1})
                else:
                    perform_ocr(
                        {"page": index + 1},
                        lambda index=index: _ocr_pdf_page(data, index, ocr_language, ocr_timeout_seconds, max_image_pixels),
                    )
        elif extension == ".docx":
            from docx import Document
            from docx.oxml.ns import qn
            from docx.table import Table
            from docx.text.paragraph import Paragraph

            document = Document(io.BytesIO(data))
            paragraph_index = 0
            table_index = 0

            def read_table(table, prefix: dict[str, int | str]) -> None:
                for row_index, row in enumerate(table.rows, 1):
                    seen = set()
                    for column_index, cell in enumerate(row.cells, 1):
                        if cell._tc in seen:
                            continue
                        seen.add(cell._tc)
                        location = {**prefix, "row": row_index, "column": column_index}
                        for cell_index, child in enumerate(cell._tc.iterchildren(), 1):
                            if child.tag == qn("w:p"):
                                append(Paragraph(child, cell).text, {**location, "cell_paragraph": cell_index})
                            elif child.tag == qn("w:tbl"):
                                read_table(Table(child, cell), {"table": f"{prefix['table']}.{row_index}.{column_index}.{cell_index}"})

            for child in document.element.body.iterchildren():
                if child.tag == qn("w:p"):
                    paragraph_index += 1
                    append(Paragraph(child, document).text, {"paragraph": paragraph_index})
                elif child.tag == qn("w:tbl"):
                    table_index += 1
                    read_table(Table(child, document), {"table": table_index})
            # Images in DOCX are not OCR'd: text extraction is still useful, but incomplete.
            if document.element.xpath(".//w:drawing") or document.element.xpath(".//w:pict"):
                missing_text = True
                messages.append("DOCX_IMAGES_NOT_EXTRACTED: Embedded images require manual review or separate PNG/JPEG upload.")
        else:
            with _read_image(data, max_image_pixels) as image:
                perform_ocr({"image": 1}, lambda: _ocr_image(image, ocr_language, ocr_timeout_seconds))
    except DocumentError:
        raise
    except Exception as exc:
        raise _error("DOCUMENT_PARSE_FAILED", "The document could not be parsed.") from exc
    if not chunks and not missing_text:
        raise _error("EMPTY_DOCUMENT", "The document contains no extractable text.")
    status = "partial" if chunks and missing_text else "ocr_required" if missing_text else "processed"
    return ExtractionResult(status=status, chunks=chunks, warnings=messages)
