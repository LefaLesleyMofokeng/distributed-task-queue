from types import SimpleNamespace

import fakeredis
import pytest
from fastapi.testclient import TestClient
from PIL import Image

import api


class FakeResult:
    """Stands in for Celery's AsyncResult: it only needs a state and a result."""

    def __init__(self, state, result=None):
        self.state = state
        self.result = result


@pytest.fixture
def env(tmp_path, monkeypatch):
    """A complete fake world: in-memory Redis, a fake task queue and 3 tiny images."""
    # Three small test images in a temporary folder
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    for n in range(1, 4):
        Image.new("RGB", (40, 30), (n * 60, 100, 150)).save(input_dir / f"image_{n}.jpg")
    monkeypatch.setattr(api, "INPUT_DIR", input_dir)
    monkeypatch.setattr(api, "OUTPUT_DIR", tmp_path / "output")

    # An in-memory Redis that behaves like the real one (database 2 and database 0)
    server = fakeredis.FakeServer()
    fake_r = fakeredis.FakeRedis(server=server, db=2, decode_responses=True)
    fake_broker = fakeredis.FakeRedis(server=server, db=0, decode_responses=True)
    monkeypatch.setattr(api, "r", fake_r)
    monkeypatch.setattr(api, "broker", fake_broker)

    # A fake task queue: delay() records the task and leaves it PENDING
    states = {}
    calls = []

    def fake_delay(input_path, output_dir, filter_name):
        task_id = f"task-{len(calls) + 1}"
        calls.append((input_path, output_dir, filter_name))
        states[task_id] = FakeResult("PENDING")
        return SimpleNamespace(id=task_id)

    def fake_async_result(task_id, app=None):
        return states.get(task_id, FakeResult("PENDING"))

    def finish_all():
        for task_id in states:
            states[task_id] = FakeResult("SUCCESS", f"/out/{task_id}.jpg")

    monkeypatch.setattr(api, "process_image", SimpleNamespace(delay=fake_delay))
    monkeypatch.setattr(api, "AsyncResult", fake_async_result)

    return SimpleNamespace(
        client=TestClient(api.app),
        r=fake_r,
        broker=fake_broker,
        input_dir=input_dir,
        states=states,
        calls=calls,
        finish_all=finish_all,
        FakeResult=FakeResult,
    )