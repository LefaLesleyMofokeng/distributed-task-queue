import time
from tasks import slow_add

start = time.time()
results = [slow_add.delay(n, n) for n in range(1, 7)]
print(f"Submitted 6 tasks in {time.time() - start:.2f} seconds")

for r in results:
    print("Task id:", r.id)

print("Waiting for answers...")
for n, r in enumerate(results, start=1):
    print(f"slow_add({n}, {n}) =", r.get(timeout=30))

print(f"Everything finished after {time.time() - start:.1f} seconds")