import time
from pathlib import Path

from image_ops import FILTERS
from tasks import process_image

images = sorted(Path("images/input").glob("*.jpg"))
output_dir = str(Path("images/output").resolve())

start = time.time()
results = []
for i, path in enumerate(images):
    filter_name = FILTERS[i % len(FILTERS)]
    results.append(process_image.delay(str(path.resolve()), output_dir, filter_name))
print(f"Submitted {len(results)} tasks in {time.time() - start:.2f} seconds")

for r in results:
    r.get(timeout=300)
print(f"All {len(results)} images processed in {time.time() - start:.1f} seconds")