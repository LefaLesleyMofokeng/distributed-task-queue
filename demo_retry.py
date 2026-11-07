import time
from tasks import flaky_task

start = time.time()
result = flaky_task.delay("test")
print("Result:", result.get(timeout=60))
print(f"Took {time.time() - start:.1f} seconds")