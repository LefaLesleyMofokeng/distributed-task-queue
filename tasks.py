import os
import time

from celery import Celery
from PIL import UnidentifiedImageError

from image_ops import process

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")

app = Celery(
    "tasks",
    broker=f"redis://{REDIS_HOST}:6379/0",
    backend=f"redis://{REDIS_HOST}:6379/1",
)
app.conf.worker_prefetch_multiplier = 1
app.conf.task_acks_late = True  # acknowledge a task only AFTER it finishes
app.conf.broker_transport_options = {"visibility_timeout": 60}
app.conf.task_time_limit = 120  # stop any task running over 2 minutes (works with worker processes)


@app.task
def slow_add(x, y):
    """A pretend heavy task: takes 3 seconds to add two numbers."""
    time.sleep(3)
    return x + y


@app.task(
    autoretry_for=(OSError,),
    dont_autoretry_for=(UnidentifiedImageError,),
    retry_backoff=2,
    retry_backoff_max=30,
    retry_jitter=True,
    max_retries=3,
)
def process_image(input_path, output_dir, filter_name):
    """The real heavy task: filter and shrink one image."""
    return process(input_path, output_dir, filter_name)


@app.task(bind=True, max_retries=4)
def flaky_task(self, name):
    """A demo task that fails twice, then works, to show retries happening."""
    attempt = self.request.retries + 1
    print(f"flaky_task({name}): attempt {attempt}", flush=True)
    if attempt < 3:
        raise self.retry(exc=RuntimeError("temporary glitch"), countdown=2 ** attempt)
    return f"{name} succeeded on attempt {attempt}"