from pathlib import Path
from PIL import Image, ImageFilter, ImageOps

FILTERS = ["blur", "sharpen", "edges", "grayscale"]


def process(input_path, output_dir, filter_name):
    """Open one image, apply a filter, shrink it and save it. Returns the saved path."""
    img = Image.open(input_path).convert("RGB")

    if filter_name == "blur":
        img = img.filter(ImageFilter.GaussianBlur(radius=12))
    elif filter_name == "sharpen":
        img = img.filter(ImageFilter.UnsharpMask(radius=6, percent=200, threshold=2))
    elif filter_name == "edges":
        img = img.filter(ImageFilter.FIND_EDGES)
    elif filter_name == "grayscale":
        img = ImageOps.autocontrast(ImageOps.grayscale(img))
    else:
        raise ValueError(f"Unknown filter: {filter_name}")

    img.thumbnail((1200, 1200))  # shrinks in place and keeps the proportions

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{Path(input_path).stem}_{filter_name}.jpg"
    img.save(out_path, quality=85)
    return str(out_path)