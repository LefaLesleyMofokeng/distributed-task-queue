import sys
import time

import requests

BASE = "http://127.0.0.1:8000"
filter_name = sys.argv[1] if len(sys.argv) > 1 else "blur"

start = time.time()
resp = requests.post(f"{BASE}/batches", json={"filter": filter_name, "force": True})
resp.raise_for_status()
batch_id = resp.json()["batch_id"]
print("Started batch", batch_id)

while True:
    status = requests.get(f"{BASE}/batches/{batch_id}").json()
    if status["status"] != "processing":
        break
    time.sleep(0.2)

elapsed = time.time() - start
print(f"{status['status']}: {status['succeeded']} of {status['total']} images in {elapsed:.1f} seconds")