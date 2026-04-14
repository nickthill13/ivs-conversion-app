"""
converter.py — IVS Conversion App
Core conversion logic.

.IVS  = TIFF image (renamed)
.IVA  = text-based annotation overlay (same stem as .IVS)

Workflow:
  1. Open .IVS as TIFF via Pillow
  2. Parse matching .IVA if present
  3. Draw annotations onto the image
  4. Export to TIFF / PNG / JPEG / PDF
"""

import io
from pathlib import Path
from PIL import Image, ImageDraw
from reportlab.pdfgen import canvas as pdf_canvas


# ---------------------------------------------------------------------------
# Color conversion
# Windows COLORREF = 0x00BBGGRR stored as a plain integer
# ---------------------------------------------------------------------------
def colorref_to_rgb(value: int) -> tuple[int, int, int]:
    r = value & 0xFF
    g = (value >> 8) & 0xFF
    b = (value >> 16) & 0xFF
    return (r, g, b)


# ---------------------------------------------------------------------------
# IVA parser
# ---------------------------------------------------------------------------
def parse_iva(path: str) -> list[dict]:
    """Return a list of annotation objects parsed from an .IVA file."""
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        lines = [ln.rstrip("\n") for ln in f]

    objects = []
    i = 0
    while i < len(lines):
        if lines[i].strip() == "BEGINOBJECT":
            obj, i = _read_object(lines, i + 1)
            objects.append(obj)
        else:
            i += 1
    return objects


def _read_object(lines: list[str], start: int) -> tuple[dict, int]:
    obj: dict = {}
    i = start
    n = len(lines)

    obj["type"] = int(lines[i].strip())
    i += 1

    while i < n:
        token = lines[i].strip()
        if token == "ENDOBJECT":
            return obj, i + 1

        key = token
        i += 1

        if key == "POINTS":
            count = int(lines[i].strip()); i += 1
            pts = []
            for _ in range(count):
                x = float(lines[i].strip()); i += 1
                y = float(lines[i].strip()); i += 1
                pts.append((x, y))
            obj["points"] = pts

        elif key in ("SCALARX", "SCALARY", "LINEWIDTH", "FONTSIZE"):
            obj[key.lower()] = float(lines[i].strip()); i += 1

        elif key in ("OFFSETX", "OFFSETY", "TAG", "FORECOLOR", "BACKCOLOR",
                     "FONTBOLD", "FONTITALIC", "FONTSTRIKETHROUGH", "FONTUNDERLINE",
                     "LINESTYLE", "FILLPATTERN", "FILLMODE", "GROUPING",
                     "ROP2", "VISIBLE", "SHOWNAME", "NAMEAUTOADJUST"):
            obj[key.lower()] = int(lines[i].strip()); i += 1

        elif key == "HANDLES":
            count = int(lines[i].strip()); i += 1
            obj["handles"] = [int(lines[i + j].strip()) for j in range(count)]
            i += count

        elif key == "NAMEOFFSET":
            ox = float(lines[i].strip()); i += 1
            oy = float(lines[i].strip()); i += 1
            obj["nameoffset"] = (ox, oy)

        elif key == "FONTNAME":
            i += 1  # count line
            obj["fontname_raw"] = lines[i].strip(); i += 1

        elif key == "TEXT":
            obj["text"] = lines[i].strip(); i += 1

        else:
            obj[key.lower()] = lines[i].strip(); i += 1

    return obj, i


# ---------------------------------------------------------------------------
# Annotation renderer
# ---------------------------------------------------------------------------
def render_annotations(image: Image.Image, annotations: list[dict]) -> Image.Image:
    """Composite IVA annotations onto the image. Returns an RGBA image."""
    img = image.convert("RGBA")
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    for obj in annotations:
        obj_type = obj.get("type")
        if obj_type == 0:           # canvas descriptor — skip
            continue
        if not obj.get("visible", 1):
            continue

        pts = obj.get("points", [])
        if not pts:
            continue

        fg = colorref_to_rgb(obj.get("forecolor", 0))
        bg = colorref_to_rgb(obj.get("backcolor", 16777215))
        lw = max(1, int(round(obj.get("linewidth", 3.0))))
        px = [(int(round(x)), int(round(y))) for x, y in pts]

        if obj_type == 11:
            # Polyline
            if len(px) >= 2:
                draw.line(px, fill=fg + (255,), width=lw)

        elif obj_type == 6:
            # L-shaped revision marker
            if len(px) >= 2:
                draw.line(px, fill=fg + (255,), width=lw)
            if len(px) == 3:
                xs = [p[0] for p in px]
                ys = [p[1] for p in px]
                draw.rectangle([min(xs), min(ys), max(xs), max(ys)],
                               fill=bg + (70,), outline=fg + (180,))

        else:
            if len(px) >= 2:
                draw.line(px, fill=fg + (255,), width=lw)

    return Image.alpha_composite(img, overlay)


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------
def export_image(image: Image.Image, output_path: str, fmt: str) -> None:
    fmt = fmt.upper()
    if fmt == "PDF":
        _export_pdf(image, output_path)
    elif fmt == "JPEG":
        image.convert("RGB").save(output_path, format="JPEG", quality=95)
    elif fmt == "TIFF":
        image.convert("RGB").save(output_path, format="TIFF", compression="tiff_lzw")
    else:
        image.save(output_path, format="PNG")


def _export_pdf(image: Image.Image, output_path: str) -> None:
    img_rgb = image.convert("RGB")
    w, h = img_rgb.size
    buf = io.BytesIO()
    img_rgb.save(buf, format="PNG")
    buf.seek(0)
    c = pdf_canvas.Canvas(output_path, pagesize=(float(w), float(h)))
    c.drawInlineImage(img_rgb, 0, 0, width=float(w), height=float(h))
    c.save()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def convert_file(
    ivs_path: str,
    output_dir: str,
    fmt: str,
    include_markups: bool = True,
    progress_callback=None,
) -> str:
    """
    Convert a single .IVS (+ optional .IVA) to the target format.
    Returns the output file path.
    """
    def log(msg):
        if progress_callback:
            progress_callback(msg)

    ivs = Path(ivs_path)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    log(f"Opening {ivs.name}")
    image = Image.open(ivs)

    iva = ivs.with_suffix(".iva")
    if include_markups and iva.exists():
        log(f"  Applying markups from {iva.name}")
        annotations = parse_iva(str(iva))
        image = render_annotations(image, annotations)
    else:
        image = image.convert("RGBA")

    ext = {"TIFF": ".tiff", "PDF": ".pdf", "PNG": ".png", "JPEG": ".jpg"}.get(fmt.upper(), ".png")
    out_path = out_dir / (ivs.stem + ext)

    log(f"  Exporting → {out_path.name}")
    export_image(image, str(out_path), fmt)
    log(f"  Done")
    return str(out_path)


def convert_folder(
    input_dir: str,
    output_dir: str,
    fmt: str,
    include_markups: bool = True,
    progress_callback=None,
) -> list[str]:
    """Batch convert all .IVS files in a folder."""
    input_dir = Path(input_dir)
    ivs_files = sorted(input_dir.glob("*.ivs")) + sorted(input_dir.glob("*.IVS"))

    seen, unique = set(), []
    for f in ivs_files:
        if f.name.lower() not in seen:
            seen.add(f.name.lower()); unique.append(f)

    results = []
    for ivs in unique:
        try:
            out = convert_file(str(ivs), output_dir, fmt, include_markups, progress_callback)
            results.append(out)
        except Exception as e:
            if progress_callback:
                progress_callback(f"ERROR {ivs.name}: {e}")
    return results
