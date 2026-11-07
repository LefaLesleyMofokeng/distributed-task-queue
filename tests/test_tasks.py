from PIL import Image, UnidentifiedImageError

import tasks


def test_process_image_works_end_to_end_without_a_queue(tmp_path):
    source = tmp_path / "photo.jpg"
    Image.new("RGB", (1800, 1200), (10, 200, 90)).save(source)

    # Calling the task like a normal function runs it right here, with no worker
    result = tasks.process_image(str(source), str(tmp_path / "out"), "grayscale")
    assert result.endswith("photo_grayscale.jpg")


def test_retry_policy_matches_our_design():
    task = tasks.process_image
    assert OSError in task.autoretry_for
    assert UnidentifiedImageError in task.dont_autoretry_for
    assert task.max_retries == 3


def test_reliability_settings_are_on():
    assert tasks.app.conf.task_acks_late is True
    assert tasks.app.conf.worker_prefetch_multiplier == 1