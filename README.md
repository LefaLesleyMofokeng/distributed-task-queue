# Distributed Task Queue & Caching System

![Tests](https://github.com/LefaLesleyMofokeng/distributed-task-queue/actions/workflows/tests.yml/badge.svg)

A background-processing system. A FastAPI service accepts batch image-processing
jobs, puts them on a Redis queue, and a pool of Celery workers processes them in
parallel. Results are cached, failures are retried safely, and the whole system
starts with one Docker Compose command.

## How it works

```
Client --POST /batches--> API (FastAPI) --one task per image--> Redis queue
   ^                          |                                     |
   |                          | cache + batch records               v
   +--GET /batches/{id}-------+------ Redis <---results----- Workers (Celery, N copies)
        (progress)
```

1. The client sends `POST /batches` with a filter name.
2. The API checks the cache. On a miss, it queues one task per image and replies
   immediately with `202 Accepted` and a batch id.
3. Celery workers take tasks from the queue, process the images, and store results.
4. The client polls `GET /batches/{id}` to see progress and results.

## Features

- **Asynchronous processing:** the API never waits for heavy work.
- **Horizontal scaling:** `docker compose up -d --scale worker=4` adds workers
  without changing any code.
- **Caching:** results are cached in Redis for one hour. The cache key is a
  fingerprint of the filter plus each input file's name, size and modified time, so
  changing an image invalidates it automatically. Identical requests that arrive
  while a batch is running share that batch. Batches that finished with errors are
  never served from the cache, and `"force": true` bypasses the cache.
- **Reliability:**
  - Temporary errors (file and disk problems) are retried with exponential backoff
    and jitter, up to 3 times.
  - Permanent errors (a corrupt image) fail immediately with a clear message, and
    the rest of the batch still completes.
  - Tasks are acknowledged only after they finish, so a task is re-queued if a
    worker dies mid-way.
  - Each task has a time limit.
- **Observability:** `GET /stats` shows cache hits, misses, hit rate and queue
  length. `GET /batches` lists recent batches.
- **Redis data structures in use:** strings with TTL (cache), lists (queue and task
  ids), hashes (batch records), a sorted set (recent batches) and atomic counters
  (statistics).

## Quick start

Requires Docker Desktop.

```
docker compose up -d --build
docker compose exec api python make_images.py 12
```

Open http://127.0.0.1:8000/docs, then use `POST /batches` with
`{"filter": "blur"}` and poll `GET /batches/{batch_id}` for progress.

```
docker compose up -d --scale worker=4                    run 4 workers
docker compose cp api:/app/images/output_api ./docker_output     copy results out
docker compose down                                      stop (keeps data)
docker compose down -v                                   stop and delete all data
```

## API

| Method | Path | Description |
| ------ | ---- | ----------- |
| GET | `/health` | Health check |
| POST | `/batches` | Start a batch. Body: `{"filter": "blur", "force": false}`. Filters: `blur`, `sharpen`, `edges`, `grayscale`. Returns 202, or 200 if served from the cache |
| GET | `/batches/{id}` | Progress, results and any per-image errors (404 if unknown or expired) |
| GET | `/batches?limit=10` | Most recent batches |
| GET | `/stats` | Cache hit rate and number of tasks waiting in the queue |

## Performance

Test setup: 12 images of 6000x4500 pixels, one filter (blur). Windows 11, 8 logical
processors, 8GB RAM, Docker Desktop (WSL 2) limited to 3GB and 4 processors. Times
are for the whole batch.

| Workers | Threads in one worker | Speed-up | Separate worker containers | Speed-up |
| ------- | --------------------- | -------- | -------------------------- | -------- |
| 1 | 12.1 s | 1.0x | 11.6 s | 1.0x |
| 2 | 7.2 s | 1.7x | 9.1 s | 1.3x |
| 4 | 5.3 s | 2.3x | 6.1 s | 1.9x |

A plain loop with no queue took about 12 s, so the queue itself adds very little
overhead.

**What the results show.** More workers help in both setups, but scaling is well
short of linear. I expected separate processes to beat threads, and they did not on
this machine. Likely reasons (I did not isolate the cause): Pillow releases the GIL
during most of its heavy work, so threads were already efficient; the Docker VM was
limited to 4 processors while the threaded run could use all 8 logical processors;
8 logical processors are probably 4 physical cores; and all workers share memory
bandwidth and disk. Each task took about 1 s alone but about 2 s when four ran
together, which points to shared-resource contention rather than queue overhead.

To reproduce: `pip install requests`, then `python bench.py` with the stack running
(it uses `"force": true` so the cache is bypassed).

## Tests

```
pip install -r requirements-dev.txt
python -m pytest -v
```

25 tests run in about two seconds with no Docker, Redis or workers: an in-memory
Redis (`fakeredis`) and a fake task queue stand in for the real ones. They cover the
image filters, cache hits, misses, forced runs and invalidation, progress tracking,
failure handling, statistics, error codes and the Celery retry settings.

## Project structure

```
api.py              FastAPI service (endpoints, caching, progress)
tasks.py            Celery app and tasks (retries, late acks)
image_ops.py        The image processing itself (independent of Celery)
make_images.py      Generates test images
bench.py            Benchmark script
docker-compose.yml  Redis, API and workers
Dockerfile          Image used by the API and the workers
tests/              Automated tests
```

The remaining scripts (`hello_redis.py`, `explore_redis.py`, `producer.py`,
`worker.py`, `sequential.py`, `submit.py`, `submit_batch.py`, `demo_retry.py`) are
learning exercises from building the project up, including a hand-made Redis queue.

## Design decisions

- **Image code is separate from Celery,** so it can be tested and run on its own.
- **The Redis address comes from an environment variable,** so the same code runs
  on a laptop and inside Docker.
- **Fails fast on permanent errors** and retries only temporary ones.
- **API and workers share a Docker volume** so file paths mean the same thing to
  both. In the cloud this would be object storage such as S3.

## Limitations and possible improvements

- Progress is calculated by checking each task's state on every request. A Redis
  counter updated by the workers would scale better.
- The containers run as root. A non-root user would be safer.
- No authentication or rate limiting on the API.
- Deploy to the cloud (for example AWS: containers on ECS, SQS as the queue, S3 for
  files) and add monitoring such as Flower.