from pathlib import Path

import pytest
from PIL import Image, UnidentifiedImageError

from image_ops import FILTERS, process


@pytest.fixture
def sample_image(tmp_path):
    path = tmp_path / "sample.jpg"
    Image.new("RGB", (1800, 1200), (200, 80, 40)).save(path)
    return path


@pytest.mark.parametrize("filter_name", FILTERS)
def test_each_filter_saves_a_shrunken_image(sample_image, tmp_path, filter_name):
    out = process(sample_image, tmp_path / "out", filter_name)
    assert Path(out).exists()
    assert out.endswith(f"sample_{filter_name}.jpg")
    with Image.open(out) as result:
        assert max(result.size) <= 1200


def test_proportions_are_kept(sample_image, tmp_path):
    out = process(sample_image, tmp_path / "out", "blur")
    with Image.open(out) as result:
        assert result.size == (1200, 800)  # 1800x1200 shrunk by the same ratio


def test_output_folder_is_created_if_missing(sample_image, tmp_path):
    target = tmp_path / "does" / "not" / "exist"
    process(sample_image, target, "sharpen")
    assert target.exists()


def test_unknown_filter_raises_value_error(sample_image, tmp_path):
    with pytest.raises(ValueError):
        process(sample_image, tmp_path / "out", "sepia")


def test_corrupt_file_raises_unidentified_image_error(tmp_path):
    broken = tmp_path / "broken.jpg"
    broken.write_text("this is not a real image")
    with pytest.raises(UnidentifiedImageError):
        process(broken, tmp_path / "out", "blur")