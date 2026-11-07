import redis

# Connect to the Redis container we started
r = redis.Redis(host="localhost", port=6379, decode_responses=True)

print("Ping:", r.ping())

r.set("greeting", "Hello from Python")
print("Value:", r.get("greeting"))

r.set("visits", 0)
r.incr("visits")
r.incr("visits")
print("Visits:", r.get("visits"))