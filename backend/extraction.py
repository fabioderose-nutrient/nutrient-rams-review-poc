"""RAMS extraction pipeline on the Nutrient Python SDK.

One structured-extraction request per checklist section (or per group of
AI_ITEMS_PER_REQUEST items). Every checklist
item is an array field: the model returns one verbatim quote per table row,
list line or ticked option, and the SDK returns, for each element, its own
metadata: the model's confidence components (log-probability, margin,
groundedness) and the source bounding boxes on the page, which the frontend
uses to highlight the evidence without any text searching.

After extraction each quote goes through two deterministic checks: the
non-answer filter (pre-printed guidance, bare N/A) and the strikethrough
detector (rows the author deleted with a line through them).
"""

import json
import os
import re
import threading

import nutrient_sdk as ns

import answer_filter
import checklist
import strikethrough

# The native layer mis-encodes some characters (an ampersand, for example, so
# that after JSON parsing a NUL byte is left followed by the two hex digits of
# the real character). NUL is never legitimate in extracted text, so rewriting
# NUL + 2 hex digits back to that character is safe.
_NUL_ESCAPE = re.compile(chr(0) + "([0-9a-fA-F]{2})")
_BULLET = re.compile(r"^[\s\-–•·*]+")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def _clean(value):
    if isinstance(value, str):
        return _NUL_ESCAPE.sub(lambda m: chr(int(m.group(1), 16)), value)
    if isinstance(value, list):
        return [_clean(v) for v in value]
    if isinstance(value, dict):
        return {k: _clean(v) for k, v in value.items()}
    return value


def _tidy(text):
    text = _CONTROL.sub("", text)
    text = _BULLET.sub("", text)
    return re.sub(r"\s+", " ", text).strip()


# Checklist items per extraction request, 0 = a whole section in one request.
ITEMS_PER_REQUEST = int(os.environ.get("AI_ITEMS_PER_REQUEST", "0"))

_sdk_lock = threading.Lock()
_initialized = False


def _ensure_sdk():
    global _initialized
    if _initialized:
        return
    key = os.environ.get("NUTRIENT_LICENSE_KEY", "").strip()
    if key:
        ns.License.register_key(key)
    _initialized = True


def _document_settings():
    s = ns.DocumentSettings()
    vision = s.vision_settings
    vision.engine = ns.VisionEngine.ICR
    # VISION_FEATURES: comma-separated VisionFeatures names (TABLE, FORM,
    # KEY_VALUE_REGION, HANDWRITING...), empty = the SDK default (all of them).
    # Table and form detection keep the rows and cells of the RAMS together,
    # which the model needs to quote the right answer. The license must
    # include each feature.
    names = [n.strip().upper() for n in os.environ.get("VISION_FEATURES", "").split(",") if n.strip()]
    if names:
        features = 0
        for name in names:
            features |= getattr(ns.VisionFeatures, name).value
        vision.features = features
    # The layout model's default threshold (0.5) drops whole regions of
    # form-style RAMS pages (answer cells, hazard table rows, tick boxes);
    # at 0.2 those regions are kept and the model can quote them.
    s.inference_layout_settings.confidence_threshold = float(os.environ.get("LAYOUT_CONFIDENCE", "0.2"))
    ai = s.ai_processing_settings
    provider = os.environ.get("AI_PROVIDER", "openai").strip().lower()
    if provider == "ollama":
        # A local model served by Ollama, reached through the app's own relay
        # (app.py, /internal/ollama), which drops the log-probability request
        # Ollama cannot answer. Nothing leaves the machine.
        ai.provider = "local"
        ai.api_key = "ollama"
        ai.model = os.environ.get("AI_MODEL", "") or "qwen2.5:7b-instruct"
        ai.endpoint = f"http://127.0.0.1:{os.environ.get('PORT', '8080')}/internal/ollama/v1"
    else:
        ai.provider = provider
        ai.api_key = os.environ.get("AI_API_KEY", "")
        ai.model = os.environ.get("AI_MODEL", "") or "gpt-4o"
        endpoint = os.environ.get("AI_ENDPOINT", "").strip()
        if endpoint:
            ai.endpoint = endpoint
    ai.include_confidence = True
    ai.include_source_locations = True
    ai.include_groundedness = True
    # Page images did not change any answer on the sample packs (tick marks
    # reach the model through the text once the layout threshold is lowered)
    # and they cost image tokens, so they are opt-in.
    ai.include_page_images = os.environ.get("AI_PAGE_IMAGES", "0") == "1"
    ai.temperature = 0.0
    return s


def _confidence_percent(meta):
    if not meta:
        return 0
    comp = meta.get("confidenceComponents") or {}
    prob = comp.get("probabilityScore")
    grounding = comp.get("groundingScore")
    if prob is None and grounding is None:
        return 0
    prob = 1.0 if prob is None else float(prob)
    grounding = 1.0 if grounding is None else float(grounding)
    return round(prob * grounding * 100)


def _boxes(meta):
    if not meta:
        return []
    boxes = []
    for src in meta.get("source_bboxes") or []:
        bbox = src.get("bbox") or {}
        if bbox.get("width") and bbox.get("height"):
            boxes.append({"page": src.get("page"), **{k: bbox[k] for k in ("x", "y", "width", "height")}})
    if not boxes and meta.get("bbox"):
        bbox = meta["bbox"]
        if bbox.get("width") and bbox.get("height"):
            boxes.append({"page": meta.get("page"), **{k: bbox[k] for k in ("x", "y", "width", "height")}})
    # Short quotes (a date, a name) are grounded at every occurrence
    # in the document; keep the ones on the page the SDK picked as primary.
    primary = meta.get("page")
    on_primary = [b for b in boxes if b.get("page") == primary]
    return (on_primary or boxes)[:8]


def _elements(values, metas, limit, renders):
    """Turn the model's quotes into kept evidence elements."""
    if isinstance(values, str):
        values = [values]
    if isinstance(metas, dict):
        metas = [metas]
    elif not isinstance(metas, list):
        metas = []
    kept = []
    seen = set()
    for index, value in enumerate(values or []):
        if not isinstance(value, str):
            continue
        text = _tidy(value)
        # The model sometimes returns pre-printed form guidance or a bare
        # "N/A" with high confidence; only a real answer counts.
        if not text or not answer_filter.is_real_answer(text):
            continue
        norm = re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()
        if norm in seen:
            continue
        meta = metas[index] if index < len(metas) and isinstance(metas[index], dict) else None
        boxes = _boxes(meta)
        if boxes:
            boxes = renders.keep_boxes(boxes)
            if not boxes:
                continue
        seen.add(norm)
        kept.append({
            "text": text,
            "confidence": _confidence_percent(meta),
            "page": (meta or {}).get("page"),
            "boxes": boxes,
        })
        if len(kept) >= limit:
            break
    return kept


def process_document(path, progress=None):
    _ensure_sdk()
    with _sdk_lock:
        settings = _document_settings()
        doc = ns.Document.open(path, settings)
        renders = None
        try:
            page_count = doc.get_page_count()
            vision = ns.Vision.set(doc)
            sections = []
            pages_info = []
            for index, (section_key, section_label, items) in enumerate(checklist.ALL_ITEMS):
                if progress is not None:
                    progress(f"Reviewing the {section_label.replace('Does the ', '').replace('...', '')} checklist",
                             index, len(checklist.ALL_ITEMS))
                # One request per section by default. A small local model
                # answers better when it gets a few items at a time
                # (AI_ITEMS_PER_REQUEST=3).
                size = ITEMS_PER_REQUEST or len(items)
                extraction, metadata = {}, {}
                for start in range(0, len(items), size):
                    request = ns.StructuredExtractionRequest()
                    request.schema = json.dumps(checklist.build_schema(items[start:start + size]))
                    request.instructions = checklist.instructions_for(section_key)
                    result = _clean(json.loads(vision.extract_structured(request)))
                    extraction.update(result.get("extraction") or {})
                    metadata.update(result.get("metadata") or {})
                    pages_info = result.get("pages") or pages_info
                if renders is None:
                    renders = strikethrough.PageRenders(doc, pages_info)
                built = []
                found = 0
                for key, label, detail, limit in items:
                    elements = _elements(extraction.get(key), metadata.get(key), limit, renders)
                    present = bool(elements)
                    if present:
                        found += 1
                    boxes = [b for e in elements for b in e["boxes"]]
                    built.append({
                        "key": key,
                        "label": label,
                        "question": detail,
                        "answer": "YES" if present else "NO",
                        "evidence": elements,
                        "confidence": round(sum(e["confidence"] for e in elements) / len(elements)) if present else 0,
                        "page": elements[0]["page"] if present else None,
                        "boxes": boxes,
                    })
                sections.append({
                    "key": section_key,
                    "label": section_label,
                    "found": found,
                    "total": len(items),
                    "items": built,
                })
            return {
                "page_count": page_count,
                "pages": pages_info,
                "checklists": sections,
                "strikethrough_check": {
                    "active": renders is not None and renders.active,
                    "error": renders.error if renders is not None else "no extraction result",
                },
            }
        finally:
            if renders is not None:
                renders.close()
            doc.close()
