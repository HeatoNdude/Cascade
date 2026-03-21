"""Test 3: API route verification"""
import httpx
import time

BASE = "http://127.0.0.1:5001"

def test(label, method, path, json_body=None):
    try:
        if method == "GET":
            r = httpx.get(f"{BASE}{path}", timeout=10)
        else:
            r = httpx.post(f"{BASE}{path}", json=json_body, timeout=10)
        print(f"[{r.status_code}] {label}")
        data = r.json()
        # Print first 500 chars of response
        import json
        text = json.dumps(data, indent=2)[:500]
        print(text)
        print()
        return data
    except Exception as e:
        print(f"[FAIL] {label}: {e}")
        print()
        return None

# 1. Health
test("GET /health", "GET", "/health")

# 2. Graph status (should show ready since we already opened)
data = test("GET /graph/status", "GET", "/graph/status")

# If not ready, the build from the previous /graph/open call should already be done
if data and data.get("status") != "ready":
    print("Status not ready, waiting...")
    for i in range(30):
        time.sleep(2)
        data = httpx.get(f"{BASE}/graph/status", timeout=10).json()
        print(f"  poll {i}: {data.get('status')}")
        if data.get("status") == "ready":
            break

# 3. Nodes
test("GET /graph/nodes", "GET", "/graph/nodes?limit=5")

# 4. Stats
test("GET /graph/stats", "GET", "/graph/stats")

# 5. Search
test("POST /graph/search", "POST", "/graph/search", {"query": "file watching", "top_k": 5})

print("=== All API tests complete ===")
