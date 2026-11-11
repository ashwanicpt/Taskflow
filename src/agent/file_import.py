from io import BytesIO
import re

from docx import Document
from fastapi import HTTPException
from openpyxl import load_workbook

from src.agent.task_agent import client, extract_json

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_TASKS = 100


def extract_tasks_from_file(filename: str, content: bytes) -> list[dict[str, str]]:
    extension = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if extension == "xlsx":
        return _extract_excel_tasks(content)
    if extension == "docx":
        return _extract_word_tasks(content)
    raise HTTPException(status_code=415, detail="Upload a .docx or .xlsx file")


def _normalize_header(value) -> str:
    return re.sub(r"[^a-z]", "", str(value or "").strip().lower())


def _header_indexes(row):
    normalized = [_normalize_header(value) for value in row]
    title_index = next((i for i, value in enumerate(normalized) if value in {"title", "tasktitle"}), None)
    description_index = next((i for i, value in enumerate(normalized) if value in {"description", "taskdescription"}), None)
    if title_index is None or description_index is None:
        return None
    return title_index, description_index


def _task_rows(rows, header_row_index: int) -> list[dict[str, str]]:
    indexes = _header_indexes(rows[header_row_index])
    if not indexes:
        return []

    title_index, description_index = indexes
    tasks = []
    for row_number, row in enumerate(rows[header_row_index + 1:], start=header_row_index + 2):
        title = row[title_index] if title_index < len(row) else None
        description = row[description_index] if description_index < len(row) else None
        if title is None and description is None:
            continue
        if title is None or not str(title).strip():
            raise HTTPException(status_code=400, detail=f"Row {row_number} is missing a title")
        tasks.append({
            "title": str(title).strip(),
            "description": str(description).strip() if description is not None else ""
        })
        if len(tasks) > MAX_TASKS:
            raise HTTPException(status_code=400, detail=f"A file can contain at most {MAX_TASKS} tasks")
    return tasks


def _extract_excel_tasks(content: bytes) -> list[dict[str, str]]:
    try:
        workbook = load_workbook(BytesIO(content), read_only=True, data_only=True)
        worksheet = workbook.active
        if not worksheet.max_row or not worksheet.max_column:
            raise HTTPException(status_code=400, detail="The spreadsheet is empty")
        if worksheet.max_row > MAX_TASKS + 10:
            raise HTTPException(status_code=400, detail=f"A file can contain at most {MAX_TASKS} tasks")

        rows = list(worksheet.iter_rows(
            max_row=worksheet.max_row,
            max_col=min(worksheet.max_column, 100),
            values_only=True
        ))
        header_row_index = next((i for i, row in enumerate(rows) if _header_indexes(row)), None)
        if header_row_index is None:
            raise HTTPException(status_code=400, detail="Spreadsheet needs title and description columns")

        tasks = _task_rows(rows, header_row_index)
        if not tasks:
            raise HTTPException(status_code=400, detail="No tasks were found in the spreadsheet")
        return tasks
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Could not read this Excel file") from exc


def _extract_word_tasks(content: bytes) -> list[dict[str, str]]:
    try:
        document = Document(BytesIO(content))
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Could not read this Word document") from exc

    table_tasks = []
    text_parts = [paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip()]
    for table in document.tables:
        rows = [[cell.text.strip() for cell in row.cells] for row in table.rows]
        table_tasks.extend(_task_rows(rows, 0) if rows and _header_indexes(rows[0]) else [])
        text_parts.extend(" | ".join(row) for row in rows)
    if table_tasks:
        if len(table_tasks) > MAX_TASKS:
            raise HTTPException(status_code=400, detail=f"A file can contain at most {MAX_TASKS} tasks")
        return table_tasks

    document_text = "\n".join(text_parts).strip()
    if not document_text:
        raise HTTPException(status_code=400, detail="The Word document contains no readable text")

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=f"""Extract every task from this document. Return only JSON in this format:
{{"tasks":[{{"title":"...","description":"..."}}]}}
Do not invent tasks. Include a task only when its title is present. Limit the result to {MAX_TASKS} tasks.

Document text:
{document_text[:30000]}"""
        )
        result = extract_json(response.text or "")
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Could not extract tasks from the Word document") from exc

    tasks = result.get("tasks") if isinstance(result, dict) else result
    if not isinstance(tasks, list):
        raise HTTPException(status_code=422, detail="No task list could be extracted from the Word document")
    if len(tasks) > MAX_TASKS:
        raise HTTPException(status_code=400, detail=f"A file can contain at most {MAX_TASKS} tasks")

    normalized_tasks = []
    for item in tasks:
        if not isinstance(item, dict):
            continue
        data = item.get("data") if isinstance(item.get("data"), dict) else item
        title = str(data.get("title") or "").strip()
        if title:
            normalized_tasks.append({
                "title": title,
                "description": str(data.get("description") or "").strip()
            })
    if not normalized_tasks:
        raise HTTPException(status_code=422, detail="No tasks with titles were found in the Word document")
    return normalized_tasks