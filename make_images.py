import os
import sys
from pathlib import Path

from PIL import Image

SIZE = (6000, 4500)  # width and height in pixels; bigger means slower tasks
count = int(sys.argv[1]) if len(sys.argv) > 1 else 12

folder = Path("images/input")
folder.mkdir(parents=True, exist_ok=True)

for n in range(1, count + 1):
    # Make a tiny image of random colours, then stretch it. The result is smooth,
    # colourful abstract art, with no need to download any pictures.
    small = Image.frombytes("RGB", (40, 30), os.urandom(40 * 30 * 3))
    big = small.resize(SIZE, Image.Resampling.BICUBIC)
    path = folder / f"image_{n:02d}.jpg"
    big.save(path, quality=90)
    print("Created", path)