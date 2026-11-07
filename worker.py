import json
import sys
import time
import redis

r = redis.Redis(host="localhost", port=6379, decode_responses=True)

# Give each worker a name so we can tell them apart. Run like:  python worker.py A
worker_name = sys.argv[1] if len(sys.argv) > 1 else "worker"

print(f"[{worker_name}] waiting for jobs... (press Ctrl+C to stop)")

while True:
    # Wait here until a job arrives. timeout=0 means wait forever.
    queue_name, payload = r.brpop("queue:jobs", timeout=0)
    job = json.loads(payload)
    job_id = job["id"]

    r.hset(f"job:{job_id}", mapping={"status": "running", "worker": worker_name})
    print(f"[{worker_name}] started job {job_id}")

    time.sleep(job["seconds"])  # pretend this is heavy work

    r.hset(f"job:{job_id}", mapping={"status": "done"})
    print(f"[{worker_name}] finished job {job_id}")