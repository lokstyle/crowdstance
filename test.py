import requests
import json
import time

BASE_URL = "http://localhost:8000"

def test(name, passed, detail=""):
    status = "✓ PASS" if passed else "✗ FAIL"
    print(f"{status} — {name}")
    if not passed and detail:
        print(f"       {detail}")

def run_tests():
    print("\n=== CrowdStance Test Suite ===\n")

    # 1. Health check
    try:
        r = requests.get(f"{BASE_URL}/health")
        test("Health endpoint", r.status_code == 200)
        data = r.json()
        test("Health returns status ok", data.get("status") == "ok")
    except Exception as e:
        test("Health endpoint", False, str(e))

    # 2. Frontend loads
    try:
        r = requests.get(f"{BASE_URL}/")
        test("Frontend loads", r.status_code == 200)
        test("Frontend is HTML", "CrowdStance" in r.text)
    except Exception as e:
        test("Frontend loads", False, str(e))

    # 3. Empty query rejected
    try:
        r = requests.post(f"{BASE_URL}/analyze", json={"query": ""})
        test("Empty query rejected", r.status_code == 400)
    except Exception as e:
        test("Empty query rejected", False, str(e))

    # 4. Basic analysis
    try:
        print("\n  Running analysis for 'remote work' (may take 20-30s)...")
        r = requests.post(f"{BASE_URL}/analyze", json={
            "query": "remote work",
            "platform": "both",
            "limit": 10,
            "time_filter": "all"
        }, timeout=120)
        test("Analyze endpoint returns 200", r.status_code == 200)
        data = r.json()
        test("Response has query field", "query" in data)
        test("Response has grouped field", "grouped" in data)
        test("Response has FOR/AGAINST/NUANCED", all(k in data["grouped"] for k in ["FOR","AGAINST","NUANCED"]))
        test("Response has divergence", "divergence" in data)
        test("Response has summaries", "summaries" in data)
        test("Response has confidence_distribution", "confidence_distribution" in data)
        test("Response has top_keywords", "top_keywords" in data)
        test("Total comments > 0", data.get("total", 0) > 0, f"Got {data.get('total')} comments")
        test("No error in response", data.get("error") is None, data.get("error"))
    except Exception as e:
        test("Analyze endpoint", False, str(e))

    # 5. Cache test
    try:
        print("\n  Testing cache (same query again)...")
        r = requests.post(f"{BASE_URL}/analyze", json={
            "query": "remote work",
            "platform": "both",
            "limit": 10,
            "time_filter": "all"
        }, timeout=30)
        data = r.json()
        test("Cache hit works", data.get("cached") == True)
    except Exception as e:
        test("Cache test", False, str(e))

    # 6. Query intelligence
    try:
        r = requests.post(f"{BASE_URL}/intelligence", json={"query": "electric vehicles"})
        test("Intelligence endpoint returns 200", r.status_code == 200)
        data = r.json()
        test("Intelligence returns core_topic", "core_topic" in data)
        test("Intelligence returns aspects", "aspects" in data and len(data["aspects"]) > 0)
    except Exception as e:
        test("Intelligence endpoint", False, str(e))

    # 7. Empty intelligence query rejected
    try:
        r = requests.post(f"{BASE_URL}/intelligence", json={"query": ""})
        test("Empty intelligence query rejected", r.status_code == 400)
    except Exception as e:
        test("Empty intelligence rejected", False, str(e))

    # 8. Reddit only
    try:
        print("\n  Testing Reddit-only search...")
        r = requests.post(f"{BASE_URL}/analyze", json={
            "query": "crypto",
            "platform": "reddit",
            "limit": 10,
            "time_filter": "all"
        }, timeout=120)
        data = r.json()
        test("Reddit-only returns results", data.get("total", 0) > 0)
        test("Reddit-only has no HN comments", data.get("hn_count", 0) == 0)
    except Exception as e:
        test("Reddit-only search", False, str(e))

    # 9. HN only
    try:
        print("\n  Testing HN-only search...")
        r = requests.post(f"{BASE_URL}/analyze", json={
            "query": "crypto",
            "platform": "hackernews",
            "limit": 10,
            "time_filter": "all"
        }, timeout=120)
        data = r.json()
        test("HN-only returns results", data.get("total", 0) > 0)
        test("HN-only has no Reddit comments", data.get("reddit_count", 0) == 0)
    except Exception as e:
        test("HN-only search", False, str(e))

    # 10. Compare endpoint
    try:
        print("\n  Testing compare endpoint...")
        r = requests.post(f"{BASE_URL}/compare", json={
            "query_a": "remote work",
            "query_b": "crypto",
            "platform": "hackernews",
            "limit": 10
        }, timeout=120)
        test("Compare endpoint returns 200", r.status_code == 200)
        data = r.json()
        test("Compare returns a and b", "a" in data and "b" in data)
        test("Compare a has query", data["a"].get("query") == "remote work")
        test("Compare b has query", data["b"].get("query") == "crypto")
    except Exception as e:
        test("Compare endpoint", False, str(e))

    # 11. Unknown topic (low results)
    try:
        r = requests.post(f"{BASE_URL}/analyze", json={
            "query": "xyzabcdefgh123456",
            "platform": "both",
            "limit": 10
        }, timeout=60)
        data = r.json()
        test("Unknown topic handles gracefully", "error" in data)
    except Exception as e:
        test("Unknown topic handling", False, str(e))

    # 12. Subreddit filter
    try:
        print("\n  Testing subreddit filter...")
        r = requests.post(f"{BASE_URL}/analyze", json={
            "query": "electric vehicles",
            "platform": "reddit",
            "subreddit": "electricvehicles",
            "limit": 10
        }, timeout=120)
        data = r.json()
        test("Subreddit filter works", data.get("total", 0) > 0)
    except Exception as e:
        test("Subreddit filter", False, str(e))

    print("\n=== Tests Complete ===\n")

if __name__ == "__main__":
    run_tests()