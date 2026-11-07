import time

from PIL import Image


def post(env, filter_name="blur", **extra):
    return env.client.post("/batches", json={"filter": filter_name, **extra})


def test_health(env):
    assert env.client.get("/health").json() == {"status": "ok"}


def test_creating_a_batch_returns_202_and_queues_one_task_per_image(env):
    response = post(env)
    assert response.status_code == 202
    body = response.json()
    assert body["total"] == 3
    assert body["cached"] is False
    assert len(env.calls) == 3
    assert all(call[2] == "blur" for call in env.calls)


def test_repeat_request_is_served_from_cache(env):
    first = post(env).json()
    second = post(env)
    assert second.status_code == 200
    assert second.json()["cached"] is True
    assert second.json()["batch_id"] == first["batch_id"]
    assert len(env.calls) == 3  # no new tasks were queued


def test_force_skips_the_cache(env):
    first = post(env).json()
    second = post(env, force=True)
    assert second.status_code == 202
    assert second.json()["cached"] is False
    assert second.json()["batch_id"] != first["batch_id"]
    assert len(env.calls) == 6


def test_different_filter_is_not_a_cache_hit(env):
    first = post(env, "blur").json()
    second = post(env, "sharpen")
    assert second.status_code == 202
    assert second.json()["batch_id"] != first["batch_id"]


def test_changing_an_image_invalidates_the_cache(env):
    post(env)
    # Replace one image with a differently sized one
    Image.new("RGB", (80, 60), (1, 2, 3)).save(env.input_dir / "image_1.jpg")
    second = post(env)
    assert second.status_code == 202
    assert second.json()["cached"] is False


def test_progress_goes_from_processing_to_done(env):
    batch_id = post(env).json()["batch_id"]

    status = env.client.get(f"/batches/{batch_id}").json()
    assert status["status"] == "processing"
    assert status["progress_percent"] == 0

    env.states["task-1"] = env.FakeResult("SUCCESS", "/out/1.jpg")
    status = env.client.get(f"/batches/{batch_id}").json()
    assert status["status"] == "processing"
    assert status["progress_percent"] == 33

    env.finish_all()
    status = env.client.get(f"/batches/{batch_id}").json()
    assert status["status"] == "done"
    assert status["progress_percent"] == 100
    assert len(status["outputs"]) == 3


def test_failed_task_is_reported_and_the_batch_is_not_reused(env):
    batch_id = post(env).json()["batch_id"]
    env.finish_all()
    env.states["task-2"] = env.FakeResult("FAILURE", Exception("cannot identify image file"))

    status = env.client.get(f"/batches/{batch_id}").json()
    assert status["status"] == "finished_with_errors"
    assert status["succeeded"] == 2
    assert status["failed"] == 1
    assert "cannot identify" in status["errors"][0]["error"]

    # A batch with errors must never be served from the cache
    again = post(env)
    assert again.status_code == 202
    assert again.json()["cached"] is False


def test_unknown_batch_returns_404(env):
    assert env.client.get("/batches/nope").status_code == 404


def test_invalid_filter_returns_422(env):
    assert post(env, "sepia").status_code == 422


def test_no_images_returns_400(env):
    for image in env.input_dir.glob("*.jpg"):
        image.unlink()
    assert post(env).status_code == 400


def test_stats_count_hits_misses_and_waiting_tasks(env):
    post(env)  # a miss
    post(env)  # a hit
    env.broker.rpush("celery", "task-a", "task-b")  # two tasks waiting in the queue

    stats = env.client.get("/stats").json()
    assert stats["cache_hits"] == 1
    assert stats["cache_misses"] == 1
    assert stats["hit_rate_percent"] == 50
    assert stats["tasks_waiting_in_queue"] == 2
    assert stats["batches_remembered"] == 1


def test_recent_batches_are_listed_newest_first_without_outputs(env):
    first = post(env, "blur").json()["batch_id"]
    time.sleep(0.05)  # make sure the two batches get different timestamps
    second = post(env, "sharpen").json()["batch_id"]

    listing = env.client.get("/batches").json()
    assert [b["batch_id"] for b in listing] == [second, first]
    assert all("outputs" not in b for b in listing)


def test_expired_batches_disappear_from_the_recent_list(env):
    batch_id = post(env).json()["batch_id"]
    env.r.delete(f"batch:{batch_id}")  # simulate Redis expiring it

    assert env.client.get("/batches").json() == []
    assert env.r.zcard("batches:recent") == 0