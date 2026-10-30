"""Struck-through text detector.

RAMS authors delete table rows by striking them through, and the OCR text
carries no trace of that line. So for every piece of evidence the model
quotes, the page is rendered by the Nutrient SDK and the pixels inside the
evidence's own bounding box are scanned: a text line whose middle band holds
a continuous dark run spanning most of the ink width is a strikethrough.
Evidence whose lines are mostly struck is discarded.
"""

import os
import tempfile

from PIL import Image

DARK = 140          # grey level below which a pixel counts as ink
MIN_LINE_PX = 8     # ignore thinner ink segments (table borders, noise)
MIN_RUN_PX = 30     # a dark run this long (4 mm at 200 dpi) is a drawn line, not a glyph stroke
RUN_RATIO = 0.5     # drawn lines must cover this share of the text's ink width
BAND = (0.15, 0.85) # vertical band of a text line where a strikethrough sits (excludes underlines)


def _line_struck(rows, a, b, width):
    xs = [x for y in range(a, b) for x in range(width) if rows[y][x]]
    if not xs:
        return False
    ink_w = max(xs) - min(xs) + 1
    if ink_w < 20:
        return False
    best = 0
    # A block can span several table cells, each with its own strike line
    # broken by the cell border, so the long runs of a row are summed rather
    # than requiring one continuous run.
    for y in range(a + int((b - a) * BAND[0]), a + int((b - a) * BAND[1]) + 1):
        run = 0
        covered = 0
        for x in range(width + 1):
            if x < width and rows[y][x]:
                run += 1
                continue
            if run >= MIN_RUN_PX:
                covered += run
            run = 0
        if covered > best:
            best = covered
    return best >= RUN_RATIO * ink_w


def box_is_struck(image, x, y, w, h):
    """True when most text lines inside the box (image pixel coords) are struck through."""
    x0, y0 = max(0, int(x)), max(0, int(y))
    x1, y1 = min(image.width, int(x + w) + 1), min(image.height, int(y + h) + 1)
    if x1 - x0 < 4 or y1 - y0 < 4:
        return False
    px = image.crop((x0, y0, x1, y1)).convert("L").load()
    width, height = x1 - x0, y1 - y0
    rows = [[px[i, j] < DARK for i in range(width)] for j in range(height)]
    ink = [any(r) for r in rows] + [False]
    lines, start = [], None
    for j, has in enumerate(ink):
        if has and start is None:
            start = j
        elif not has and start is not None:
            if j - start >= MIN_LINE_PX:
                lines.append((start, j))
            start = None
    if not lines:
        return False
    struck = sum(1 for a, b in lines if _line_struck(rows, a, b, width))
    return struck * 2 >= len(lines)


class PageRenders:
    """Renders the document's pages once (lazily) and answers strike checks
    for bounding boxes expressed in the extraction's page space."""

    def __init__(self, document, pages_info):
        self._document = document
        self._pages = {p["page"]: p for p in pages_info or []}
        self._dir = None
        self._images = {}
        self.error = None

    @property
    def active(self):
        return self.error is None

    def close(self):
        for image in self._images.values():
            if image is not None:
                image.close()
        self._images = {}
        if self._dir:
            self._dir.cleanup()
            self._dir = None

    def _render_all(self):
        self._dir = tempfile.TemporaryDirectory(prefix="rams-pages-")
        try:
            # The SDK writes one file per page: <base>-<n>.<ext>
            self._document.export_as_image(os.path.join(self._dir.name, "page.png"))
        except Exception as exc:  # typically a license without pdf_to_image_api
            self.error = str(exc).split(" (Error Code")[0]

    def _image(self, page):
        if page in self._images:
            return self._images[page]
        if self._dir is None:
            self._render_all()
        image = None
        if self.error is None:
            path = os.path.join(self._dir.name, f"page-{page}.png")
            if os.path.exists(path):
                image = Image.open(path)
        self._images[page] = image
        return image

    def keep_boxes(self, boxes):
        """The evidence's boxes minus the struck-through ones. An empty result
        for a non-empty input means the whole quote was deleted text."""
        kept = []
        for box in boxes:
            page = box.get("page") or 1
            image = self._image(page)
            meta = self._pages.get(page)
            if image is None or not meta or not meta.get("width") or not meta.get("height"):
                kept.append(box)
                continue
            sx = image.width / meta["width"]
            sy = image.height / meta["height"]
            if not box_is_struck(image, box["x"] * sx, box["y"] * sy, box["width"] * sx, box["height"] * sy):
                kept.append(box)
        return kept
