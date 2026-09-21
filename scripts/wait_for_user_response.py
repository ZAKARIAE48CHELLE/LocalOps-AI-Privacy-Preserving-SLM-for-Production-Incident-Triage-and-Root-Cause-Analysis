import time
import json
from pathlib import Path

response_file = Path("artifacts/phase_5/user_action_response.json")
timeout_sec = 600
start_time = time.time()

print(f"Waiting up to {timeout_sec}s for user response at {response_file}...", flush=True)

while time.time() - start_time < timeout_sec:
    if response_file.exists():
        try:
            with open(response_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            print("USER_RESPONSE_RECEIVED:", flush=True)
            print(json.dumps(data, indent=2), flush=True)
            break
        except Exception as e:
            time.sleep(1)
    time.sleep(2)
else:
    print("TIMEOUT_WAITING_FOR_USER_RESPONSE", flush=True)
