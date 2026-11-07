import json
import sys
import redis

r = redis.Redis(host="localhost", port=6379, decode_responses=True)

# How many jobs to add (default 6). Run like:  python producer.py 10
count = int(sys.argv[1]) if len(sys.argv) > 1 else 6

for _ in range(count):
    job_id = r.incr("job:counter")  # a counter that gives every job a unique id
    job = {"id": job_id, "seconds": 3}  # each "heavy task" will take 3 seconds
    r.hset(f"job:{job_id}", mapping={"status": "queued"})
    r.lpush("queue:jobs", json.dumps(job))
    print(f"Added job {job_id}")

print("Jobs waiting in the queue:", r.llen("queue:jobs"))