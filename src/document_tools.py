
"""Document extraction and context-preserving text splitting."""

from io import BytesIO
from pathlib import Path
import re

from pypdf import PdfReader
from docx import Document as WordDocument
from openpyxl import load_workbook
from pptx import Presentation

SUPPORTED_EXTENSIONS = {
    ".pdf", ".docx", ".xlsx", ".xls", ".pptx", ".txt", ".md"
}


def clean_text(text):
    text = (text or "").replace("\x00", " ").replace("\u00a0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_document(data, filename, progress_callback=None):
    ext = Path(filename).suffix.lower()

    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {ext}")

    sections = []

    def add(location, text, page=None):
        text = clean_text(text)
        if text:
            sections.append({
                "source": filename,
                "page": page,
                "location": location,
                "text": text
            })

    if ext == ".pdf":
        reader = PdfReader(BytesIO(data))
        total = len(reader.pages)

        for i, page in enumerate(reader.pages, 1):
            text = page.extract_text() or ""
            add(f"Page {i}", text, i)

            if progress_callback:
                progress_callback(i, total, f"Reading page {i} of {total}")

    elif ext == ".docx":
        doc = WordDocument(BytesIO(data))
        content = []

        for paragraph in doc.paragraphs:
            if paragraph.text.strip():
                content.append(paragraph.text.strip())

        for index, table in enumerate(doc.tables, 1):
            content.append(f"Table {index}")
            for row in table.rows:
                content.append(
                    " | ".join(cell.text.strip() for cell in row.cells)
                )

        add("Document", "\n\n".join(content))

    elif ext == ".xlsx":
        workbook = load_workbook(
            BytesIO(data), read_only=True, data_only=True
        )

        try:
            for sheet in workbook.worksheets:
                rows = []

                for row in sheet.iter_rows(values_only=True):
                    values = [
                        str(value).strip() if value is not None else ""
                        for value in row
                    ]
                    if any(values):
                        rows.append(" | ".join(values))

                add(f"Sheet: {sheet.title}", "\n".join(rows))
        finally:
            workbook.close()

    elif ext == ".xls":
        import xlrd

        workbook = xlrd.open_workbook(file_contents=data)

        for sheet in workbook.sheets():
            rows = []

            for row_index in range(sheet.nrows):
                values = [
                    str(sheet.cell_value(row_index, col)).strip()
                    for col in range(sheet.ncols)
                ]
                if any(values):
                    rows.append(" | ".join(values))

            add(f"Sheet: {sheet.name}", "\n".join(rows))

    elif ext == ".pptx":
        presentation = Presentation(BytesIO(data))

        for index, slide in enumerate(presentation.slides, 1):
            parts = []

            for shape in slide.shapes:
                if getattr(shape, "has_text_frame", False):
                    if shape.text.strip():
                        parts.append(shape.text.strip())

                if getattr(shape, "has_table", False):
                    for row in shape.table.rows:
                        parts.append(
                            " | ".join(
                                cell.text.strip() for cell in row.cells
                            )
                        )

            add(f"Slide {index}", "\n\n".join(parts), index)

    else:
        add("Text", data.decode("utf-8-sig", errors="replace"))

    return sections


def split_text(text, max_chars=1800, overlap=180):
    """Prefer paragraph and sentence boundaries when splitting."""

    paragraphs = [
        p.strip()
        for p in re.split(r"\n\s*\n", text)
        if p.strip()
    ]

    units = []

    for paragraph in paragraphs:
        if len(paragraph) <= max_chars:
            units.append(paragraph)
            continue

        sentences = re.split(
            r"(?<=[.!?])\s+(?=[A-Z0-9(\"'])",
            paragraph
        )

        current = ""

        for sentence in sentences:
            if current and len(current) + len(sentence) + 1 > max_chars:
                units.append(current)
                current = sentence
            else:
                current = f"{current} {sentence}".strip()

        if current:
            units.append(current)

    chunks = []
    current = ""

    for unit in units:
        if current and len(current) + len(unit) + 2 > max_chars:
            chunks.append(current)

            tail = current[-overlap:].strip()
            current = f"{tail}\n\n{unit}" if tail else unit
        else:
            current = f"{current}\n\n{unit}".strip()

    if current:
        chunks.append(current)

    return [item.strip() for item in chunks if item.strip()]


def split_sections(sections, size=1800, overlap=180):
    chunks = []

    for section in sections:
        parts = split_text(
            section["text"],
            max_chars=size,
            overlap=overlap
        )

        for part in parts:
            chunks.append({
                "source": section["source"],
                "page": section.get("page"),
                "location": section["location"],
                "text": part
            })

    return chunks
