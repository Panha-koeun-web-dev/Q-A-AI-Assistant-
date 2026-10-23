"""
src/document_service.py
-----------------------
Extracts clean, structured text and information from user-uploaded files and images.
Supports:
- PDF (.pdf) via pypdf
- Word documents (.docx) via python-docx
- Excel spreadsheets (.xlsx, .xls) via openpyxl
- CSV / TSV tabular files
- Code and plain text files (.py, .js, .html, .css, .json, .md, .sql, etc.)
- Images (.png, .jpg, .jpeg, .webp, .gif): OCR text extraction via Windows OCR + metadata
"""

import base64
import csv
import io
from pathlib import Path
from typing import Optional, Tuple

try:
    from PIL import Image
except ImportError:
    Image = None

# ---------------------------------------------------------------------------
# OCR via Windows Media OCR (built into Windows 10/11)
# ---------------------------------------------------------------------------
_OCR_AVAILABLE = False
try:
    import winsdk.windows.media.ocr as win_ocr
    import winsdk.windows.graphics.imaging as win_imaging
    import winsdk.windows.storage.streams as win_streams
    _OCR_AVAILABLE = True
except Exception:
    _OCR_AVAILABLE = False


def _run_windows_ocr_sync(image_bytes: bytes) -> str:
    """Runs Windows native OCR synchronously on image bytes."""
    if not _OCR_AVAILABLE:
        return ""

    import asyncio

    async def _async_ocr():
        try:
            stream = win_streams.InMemoryRandomAccessStream()
            writer = win_streams.DataWriter(stream)
            writer.write_bytes(bytearray(image_bytes))
            await writer.store_async()
            stream.seek(0)

            decoder = await win_imaging.BitmapDecoder.create_async(stream)
            bitmap = await decoder.get_software_bitmap_async()

            engine = win_ocr.OcrEngine.try_create_from_user_profile_languages()
            if not engine:
                return ""
            result = await engine.recognize_async(bitmap)
            return (result.text or "").strip()
        except Exception:
            return ""

    try:
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        if loop.is_running():
            # If already inside an asyncio loop
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                return executor.submit(lambda: asyncio.run(_async_ocr())).result(timeout=10)
        else:
            return loop.run_until_complete(_async_ocr())
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Extractors for each file type
# ---------------------------------------------------------------------------

def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extracts all text from a PDF file using pypdf."""
    try:
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(file_bytes))
        pages_text = []
        for i, page in enumerate(reader.pages):
            text = (page.extract_text() or "").strip()
            if text:
                pages_text.append(f"--- Page {i + 1} ---\n{text}")
        if not pages_text:
            return "(PDF document opened, but no selectable text was found. It may consist of scanned images.)"
        return "\n\n".join(pages_text)
    except Exception as exc:
        return f"(Could not read PDF: {exc})"


def extract_text_from_docx(file_bytes: bytes) -> str:
    """Extracts all text and tables from a .docx file using python-docx."""
    try:
        import docx
        doc = docx.Document(io.BytesIO(file_bytes))
        lines = []

        # Extract paragraphs
        for p in doc.paragraphs:
            text = p.text.strip()
            if text:
                lines.append(text)

        # Extract tables
        for t_idx, table in enumerate(doc.tables):
            lines.append(f"\n[Table {t_idx + 1}]")
            for row in table.rows:
                row_cells = [cell.text.strip().replace("\n", " ") for cell in row.cells]
                lines.append(" | ".join(row_cells))

        return "\n".join(lines) if lines else "(Empty Word document)"
    except Exception as exc:
        return f"(Could not read Word document: {exc})"


def extract_text_from_xlsx(file_bytes: bytes) -> str:
    """Extracts tables from an Excel file (.xlsx) using openpyxl."""
    try:
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
        sheets_text = []

        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            rows_data = []
            for row in ws.iter_rows(values_only=True):
                # Ignore completely empty rows
                if any(v is not None for v in row):
                    formatted_row = [str(v).strip() if v is not None else "" for v in row]
                    rows_data.append(" | ".join(formatted_row))

            if rows_data:
                # Limit to first 250 rows per sheet to avoid overwhelming the model
                display_rows = rows_data[:250]
                sheet_content = "\n".join(display_rows)
                if len(rows_data) > 250:
                    sheet_content += f"\n... ({len(rows_data) - 250} more rows truncated)"
                sheets_text.append(f"[Sheet: {sheet_name}]\n{sheet_content}")

        return "\n\n".join(sheets_text) if sheets_text else "(Empty Excel workbook)"
    except Exception as exc:
        return f"(Could not read Excel file: {exc})"


def extract_text_from_csv(file_bytes: bytes) -> str:
    """Extracts and formats CSV data."""
    try:
        text = file_bytes.decode("utf-8", errors="replace")
        reader = csv.reader(io.StringIO(text))
        rows = []
        for i, row in enumerate(reader):
            if any(cell.strip() for cell in row):
                rows.append(" | ".join(cell.strip() for cell in row))
            if i >= 300:
                rows.append(f"... (truncated after 300 rows)")
                break
        return "\n".join(rows) if rows else "(Empty CSV file)"
    except Exception as exc:
        return f"(Could not read CSV: {exc})"


def process_image(file_bytes: bytes, file_name: str) -> Tuple[str, dict]:
    """
    Extracts image metadata and OCR text from an image.
    Returns (summary_text, metadata_dict).
    """
    meta_info = []
    width, height, fmt = 0, 0, "UNKNOWN"

    if Image is not None:
        try:
            with Image.open(io.BytesIO(file_bytes)) as img:
                width, height = img.size
                fmt = img.format or "IMAGE"
                meta_info.append(f"Dimensions: {width}x{height} px, Format: {fmt}")
        except Exception:
            meta_info.append("Image binary detected.")
    else:
        meta_info.append("Image binary detected.")

    # Run OCR to detect any readable text inside the image
    ocr_text = _run_windows_ocr_sync(file_bytes)
    if ocr_text:
        meta_info.append(f"\n[Extracted Text / OCR from Image]:\n{ocr_text}")
    else:
        meta_info.append("\n(No text was detected via OCR in this image)")

    return "\n".join(meta_info), {"width": width, "height": height, "format": fmt, "ocr": ocr_text}


# ---------------------------------------------------------------------------
# Main Entry Point
# ---------------------------------------------------------------------------

def process_attachment(attachment: dict) -> dict:
    """
    Processes an attachment dict:
    {
      "name": "filename.ext",
      "type": "mime/type",
      "data": "<base64>" (optional),
      "text": "plain text" (optional)
    }

    Returns an enriched attachment dict with:
    - "extracted_text": str (full human-readable content extracted)
    - "is_image": bool
    - "data": base64 string if image
    """
    name = attachment.get("name", "unnamed_file")
    mime = attachment.get("type", "").lower()
    b64_data = attachment.get("data")
    existing_text = attachment.get("text")
    ext = Path(name).suffix.lower()

    # If raw file bytes are encoded in data
    file_bytes = b""
    if b64_data:
        try:
            file_bytes = base64.b64decode(b64_data)
        except Exception:
            file_bytes = b""

    is_image = mime.startswith("image/") or ext in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".ico")

    # 1. Image
    if is_image:
        if file_bytes:
            summary, meta = process_image(file_bytes, name)
            return {
                "name": name,
                "type": mime or "image/jpeg",
                "is_image": True,
                "data": b64_data,
                "extracted_text": summary,
                "ocr_text": meta.get("ocr", ""),
            }
        return {
            "name": name,
            "type": mime or "image/jpeg",
            "is_image": True,
            "data": b64_data,
            "extracted_text": "(Image provided)",
            "ocr_text": "",
        }

    # 2. PDF Document
    if ext == ".pdf" or "pdf" in mime:
        extracted = extract_text_from_pdf(file_bytes) if file_bytes else (existing_text or "")
        return {
            "name": name,
            "type": "application/pdf",
            "is_image": False,
            "data": None,
            "extracted_text": extracted,
        }

    # 3. Word Document (.docx)
    if ext == ".docx" or "wordprocessingml" in mime:
        extracted = extract_text_from_docx(file_bytes) if file_bytes else (existing_text or "")
        return {
            "name": name,
            "type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "is_image": False,
            "data": None,
            "extracted_text": extracted,
        }

    # 4. Excel Spreadsheet (.xlsx, .xls)
    if ext in (".xlsx", ".xls") or "spreadsheetml" in mime or "excel" in mime:
        extracted = extract_text_from_xlsx(file_bytes) if file_bytes else (existing_text or "")
        return {
            "name": name,
            "type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "is_image": False,
            "data": None,
            "extracted_text": extracted,
        }

    # 5. CSV / TSV
    if ext in (".csv", ".tsv"):
        extracted = extract_text_from_csv(file_bytes) if file_bytes else (existing_text or "")
        return {
            "name": name,
            "type": "text/csv",
            "is_image": False,
            "data": None,
            "extracted_text": extracted,
        }

    # 6. Text / Code / JSON / Markdown
    if existing_text:
        return {
            "name": name,
            "type": mime or "text/plain",
            "is_image": False,
            "data": None,
            "extracted_text": existing_text,
        }

    if file_bytes:
        try:
            decoded = file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            decoded = file_bytes.decode("utf-8", errors="replace")
        return {
            "name": name,
            "type": mime or "text/plain",
            "is_image": False,
            "data": None,
            "extracted_text": decoded,
        }

    return {
        "name": name,
        "type": mime or "application/octet-stream",
        "is_image": False,
        "data": None,
        "extracted_text": "(Empty or unreadable file)",
    }

