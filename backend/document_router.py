import os
import tempfile
import time as _time
import uuid as _uuid
import threading as _threading
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from typing import Optional, Dict

from backend.document_analyzer import DocumentAnalyzer, REGISTER_KEYWORDS
from backend.token_counter import count_tokens as _count_t

router = APIRouter(prefix="/api/document", tags=["document"])
_UPLOAD_DIR = None
_DA_CACHE = None
_EXT_CACHE = None

# ── Document compression session store ──
_DOC_TASKS: Dict[str, dict] = {}


def _get_analyzer():
    global _DA_CACHE
    if _DA_CACHE is None:
        _DA_CACHE = DocumentAnalyzer()
    return _DA_CACHE


def _supported_ext_set():
    global _EXT_CACHE
    if _EXT_CACHE is None:
        _EXT_CACHE = set(_get_analyzer().supported_extensions())
    return _EXT_CACHE


def _get_upload_dir() -> str:
    global _UPLOAD_DIR
    if _UPLOAD_DIR is None:
        _UPLOAD_DIR = tempfile.mkdtemp(prefix="tokenforge_docs_")
    return _UPLOAD_DIR


@router.get("/formats")
def supported_formats():
    da = _get_analyzer()
    return {"formats": da.supported_formats_summary(), "registers": list(REGISTER_KEYWORDS.keys()) + ["general"]}


@router.post("/analyze")
async def analyze_upload(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(400, "No file provided")
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in _supported_ext_set():
        raise HTTPException(400, f"Unsupported format '{ext}'")
    data = await file.read()
    da = _get_analyzer()
    content = da.analyze_bytes(data, file.filename)
    register = da._detect_register(content.raw_text)
    return {
        "filename": file.filename,
        "format": content.detected_format,
        "size_bytes": len(data),
        "register": register,
        "tokens": _count_t(content.raw_text),
        "chars": len(content.raw_text),
        "words": len(content.raw_text.split()),
        "sections": len(content.sections) or 1,
        "tables": len(content.tables),
        "paragraphs": len(content.paragraphs) or sum(
            len(s.get("paragraphs", [])) for s in content.sections
        ) or 1,
        "preview": content.raw_text[:800],
    }


def _run_doc_compress_task(session_id: str, data: bytes, filename: str, mode: str, category: Optional[str]):
    """Run document compression in background with progress."""
    try:
        _DOC_TASKS[session_id].update({"phase": "parsing", "progress": 10})
        da = _get_analyzer()
        content = da.analyze_bytes(data, filename)
        _DOC_TASKS[session_id].update({"phase": "compressing", "progress": 40})

        compressed_text, meta = da.compress(content, mode=mode, category=category)
        _DOC_TASKS[session_id].update({"phase": "finalizing", "progress": 90})

        result = {
            **meta,
            "filename": filename,
            "format": content.detected_format,
            "original_text": content.raw_text,
            "compressed_text": compressed_text,
            "preview_original": content.raw_text[:800],
            "preview_compressed": compressed_text[:800],
        }
        _DOC_TASKS[session_id].update({
            "progress": 100, "phase": "complete", "result": result,
            "elapsed": _time.time() - _DOC_TASKS[session_id]["start_time"],
        })
    except Exception as exc:
        _DOC_TASKS[session_id].update({
            "progress": -1, "phase": "error", "error": str(exc),
        })


@router.post("/compress")
async def compress_upload(
    file: UploadFile = File(...),
    mode: str = Form("light"),
    category: Optional[str] = Form(None),
):
    if not file.filename:
        raise HTTPException(400, "No file provided")
    if mode not in ("light", "balanced", "aggressive", "max", "industrial"):
        raise HTTPException(400, "mode must be 'light', 'balanced', 'aggressive', 'max', or 'industrial'")
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in _supported_ext_set():
        raise HTTPException(400, f"Unsupported format '{ext}'")

    data = await file.read()
    session_id = _uuid.uuid4().hex[:8]
    _DOC_TASKS[session_id] = {
        "progress": 0, "phase": "queued", "start_time": _time.time(), "elapsed": 0,
    }
    _threading.Thread(
        target=_run_doc_compress_task,
        args=(session_id, data, file.filename, mode, category),
        daemon=True,
    ).start()
    return {"session_id": session_id}


@router.get("/progress/{session_id}")
def get_doc_progress(session_id: str):
    task = _DOC_TASKS.get(session_id)
    if task is None:
        raise HTTPException(404, "Task not found")
    return task
