import time
from pathlib import Path

from image_ops import FILTERS, process

images = sorted(Path("images/input").glob("*.jpg"))

start = time.time()
for i, path in enumerate(images):
    process(path, "images/output_sequential", FILTERS[i % len(FILTERS)])
    print("Done", path.name)

print(f"Processed {len(images)} images one by one in {time.time() - start:.1f} seconds")