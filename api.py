import hashlib
import os
import time
import uuid
from pathlib import Path
from typing import Literal

import redis
from celery.result import AsyncResult
from fastapi import FastAPI, HTTPException, Query, Response
from pydantic import BaseModel

from tasks import app as celery_app
from tasks import process_image

app = FastAPI(title="Image Processing Queue")

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")

# Database 2 holds our batch records and the cache (Celery uses 0 and 1)
r = redis.Redis(host=REDIS_HOST, port=6379, db=2, decode_responses=True)
# Database 0 is Celery's queue, which we only read from
broker = redis.Redis(host=REDIS_HOST, port=6379, db=0, decode_responses=True)

INPUT_DIR = Path("images/input")
OUTPUT_DIR = Path("images/output_api")
BATCH_TTL = 3600  # batch records and cache entries last 1 hour


class BatchRequest(BaseModel):
    filter: Literal["blur", "sharpen", "edges", "grayscale"]
    force: bool = False  # True means: skip the cache and always do the work


def make_cache_key(images, filter_name):
    """Make a short fingerprint of 'this filter + these exact images'."""
    parts = [filter_name]
    for path in images:
        info = path.stat()
        parts.append(f"{path.name}:{info.st_size}:{int(info.st_mtime)}")
    digest = hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]
    return f"cache:batch:{digest}"


def batch_status(batch_id):
    """Work out a batch's progress. Returns None if the batch is unknown or expired."""
    info = r.hgetall(f"batch:{batch_id}")
    if not info:
        return None

    task_ids = r.lrange(f"batch:{batch_id}:tasks", 0, -1)

    succeeded = 0
    failed = 0
    outputs = []
    errors = []
    for task_id in task_ids:
        result = AsyncResult(task_id, app=celery_app)
        if result.state == "SUCCESS":
            succeeded += 1
            outputs.append(result.result)
        elif result.state == "FAILURE":
            failed += 1
            errors.append({"task_id": task_id, "error": str(result.result)})

    total = int(info["total"])
    finished = succeeded + failed

    if finished < total:
        status = "processing"
    elif failed == 0:
        status = "done"
    else:
        status = "finished_with_errors"

    return {
        "batch_id": batch_id,
        "filter": info["filter"],
        "status": status,
        "total": total,
        "succeeded": succeeded,
        "failed": failed,
        "progress_percent": round(100 * finished / total),
        "outputs": outputs,
        "errors": errors,
    }


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/batches", status_code=202)
def create_batch(request: BatchRequest, response: Response):
    images = sorted(INPUT_DIR.glob("*.jpg"))
    if not images:
        raise HTTPException(status_code=400, detail="No images found in images/input")

    cache_key = make_cache_key(images, request.filter)

    # Step 1: look in the cache first (unless force is set)
    cached_id = r.get(cache_key)
    if cached_id and not request.force:
        existing = batch_status(cached_id)
        if existing and existing["status"] != "finished_with_errors":
            r.incr("stats:cache_hits")
            response.status_code = 200  # 200 = answer already exists
            return {
                "batch_id": cached_id,
                "total": existing["total"],
                "status": existing["status"],
                "status_url": f"/batches/{cached_id}",
                "cached": True,
            }

    # Step 2: cache miss, so do the work
    r.incr("stats:cache_misses")
    batch_id = uuid.uuid4().hex[:8]
    output_dir = str((OUTPUT_DIR / batch_id).resolve())

    task_ids = []
    for path in images:
        task = process_image.delay(str(path.resolve()), output_dir, request.filter)
        task_ids.append(task.id)

    r.hset(
        f"batch:{batch_id}",
        mapping={
            "filter": request.filter,
            "total": len(task_ids),
            "created_at": time.time(),
        },
    )
    r.rpush(f"batch:{batch_id}:tasks", *task_ids)
    r.expire(f"batch:{batch_id}", BATCH_TTL)
    r.expire(f"batch:{batch_id}:tasks", BATCH_TTL)

    # Step 3: store the answer in the cache, and note the batch in the recent list
    r.set(cache_key, batch_id, ex=BATCH_TTL)
    r.zadd("batches:recent", {batch_id: time.time()})

    return {
        "batch_id": batch_id,
        "total": len(task_ids),
        "status": "processing",
        "status_url": f"/batches/{batch_id}",
        "cached": False,
    }


@app.get("/batches/{batch_id}")
def get_batch(batch_id: str):
    status = batch_status(batch_id)
    if status is None:
        raise HTTPException(status_code=404, detail="Batch not found (or it expired)")
    return status


@app.get("/batches")
def list_batches(limit: int = Query(10, ge=1, le=50)):
    ids = r.zrevrange("batches:recent", 0, limit - 1)  # newest first
    batches = []
    for batch_id in ids:
        status = batch_status(batch_id)
        if status is None:
            r.zrem("batches:recent", batch_id)  # tidy up entries that expired
        else:
            batches.append({k: v for k, v in status.items() if k != "outputs"})
    return batches


@app.get("/stats")
def stats():
    hits = int(r.get("stats:cache_hits") or 0)
    misses = int(r.get("stats:cache_misses") or 0)
    lookups = hits + misses
    return {
        "cache_hits": hits,
        "cache_misses": misses,
        "hit_rate_percent": round(100 * hits / lookups) if lookups else 0,
        "tasks_waiting_in_queue": broker.llen("celery"),
        "batches_remembered": r.zcard("batches:recent"),
    }