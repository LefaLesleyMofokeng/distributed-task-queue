import time
import redis

r = redis.Redis(host="localhost", port=6379, decode_responses=True)

# Clean up keys left over from earlier runs of this script
r.delete("demo:session", "demo:tasks", "demo:job:1",
         "demo:tags:a", "demo:tags:b", "demo:scores")

print("--- 1. STRINGS with an expiry time (how caches work) ---")
r.set("demo:session", "user-42", ex=5)  # ex=5 means: delete after 5 seconds
print("Value now:", r.get("demo:session"))
print("Seconds left:", r.ttl("demo:session"))
time.sleep(6)
print("Value after 6 seconds:", r.get("demo:session"))

print("\n--- 2. LISTS (how queues work) ---")
r.rpush("demo:tasks", "resize image 1", "resize image 2", "resize image 3")
print("Queue length:", r.llen("demo:tasks"))
print("Whole queue:", r.lrange("demo:tasks", 0, -1))
print("Next job (taken from the front):", r.lpop("demo:tasks"))
print("Queue now:", r.lrange("demo:tasks", 0, -1))

print("\n--- 3. HASHES (a record with named fields, like a job's status) ---")
r.hset("demo:job:1", mapping={"status": "queued", "filename": "cat.jpg", "progress": 0})
r.hset("demo:job:1", "status", "running")
r.hincrby("demo:job:1", "progress", 50)
print("Job 1:", r.hgetall("demo:job:1"))

print("\n--- 4. SETS (unique items, no duplicates) ---")
r.sadd("demo:tags:a", "python", "redis", "docker")
r.sadd("demo:tags:b", "docker", "celery", "python", "python")
print("Set B (python was added twice):", sorted(r.smembers("demo:tags:b")))
print("In both sets:", sorted(r.sinter("demo:tags:a", "demo:tags:b")))
print("Is 'redis' in set A?", r.sismember("demo:tags:a", "redis"))

print("\n--- 5. SORTED SETS (items ranked by a score) ---")
r.zadd("demo:scores", {"thumbnail": 120, "report": 900, "resize": 340})
print("Fastest to slowest:", r.zrange("demo:scores", 0, -1, withscores=True))
print("Slowest task:", r.zrevrange("demo:scores", 0, 0, withscores=True))