"""
post_deployment_check.py
=========================
Run after deploying to verify the live system is healthy.
Targets the actual M3 endpoints from simulator_app.py.

Usage:
    python post_deployment_check.py
    python post_deployment_check.py --url http://your-server:5000
"""

import sys
import time
import json
import argparse
import urllib.request
import urllib.error

G = "\033[92m"; R = "\033[91m"; Y = "\033[93m"; B = "\033[1m"; X = "\033[0m"

def ok(m):   print(f"  {G}✅ PASS{X}  {m}")
def fail(m): print(f"  {R}❌ FAIL{X}  {m}")
def warn(m): print(f"  {Y}⚠️  WARN{X}  {m}")

def get(url, timeout=5):
    try:
        start = time.time()
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status, r.read().decode(), time.time() - start
    except urllib.error.HTTPError as e:
        return e.code, "", 0
    except Exception as e:
        return None, str(e), 0

def post(url, body, timeout=5):
    try:
        data = json.dumps(body).encode()
        req = urllib.request.Request(
            url, data=data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception as e:
        return None, str(e)

def run(base):
    print(f"\n{B}🏥 Patient Feedback IVR — Post-Deployment Validation{X}")
    print(f"   Target: {base}\n" + "─" * 55)
    results = []

    # 1. Health check
    status, body, ms = get(f"{base}/api/health")
    if status == 200:
        ok(f"GET /api/health → 200 ({ms*1000:.0f}ms)")
        results.append(True)
    else:
        fail(f"GET /api/health → {status}")
        results.append(False)

    # 2. Simulator UI
    status, body, ms = get(f"{base}/")
    if status == 200 and (b"<html" in body.lower().encode() or b"doctype" in body.lower().encode()):
        ok(f"GET / → HTML simulator UI ({ms*1000:.0f}ms)")
        results.append(True)
    else:
        fail(f"GET / → {status} (expected HTML)")
        results.append(False)

    # 3. Start session
    status, body = post(f"{base}/api/session/start", {})
    if status == 200:
        data = json.loads(body)
        sid = data.get("session_id")
        ok(f"POST /api/session/start → session {sid[:8]}...")
        results.append(True)
    else:
        fail(f"POST /api/session/start → {status}")
        results.append(False)
        sid = None

    # 4. Submit input (only if session started)
    if sid:
        status, body = post(f"{base}/api/session/{sid}/input", {"text": "P12345"})
        if status == 200:
            state = json.loads(body).get("state")
            ok(f"POST /api/session/{{id}}/input → state: {state}")
            results.append(True)
        else:
            fail(f"POST /api/session/{{id}}/input → {status}")
            results.append(False)

    # 5. Feedback listing
    status, body, _ = get(f"{base}/api/feedback/all")
    if status == 200:
        try:
            parsed = json.loads(body)
            ok(f"GET /api/feedback/all → {len(parsed)} record(s)")
            results.append(True)
        except Exception:
            warn("GET /api/feedback/all returned 200 but not JSON")
            results.append(False)
    else:
        fail(f"GET /api/feedback/all → {status}")
        results.append(False)

    # 6. Response time
    status, _, ms = get(f"{base}/api/health")
    if ms < 0.5:
        ok(f"Response time: {ms*1000:.0f}ms (< 500ms target)")
        results.append(True)
    else:
        warn(f"Response time: {ms*1000:.0f}ms (above 500ms target)")
        results.append(False)

    # Summary
    passed = sum(results)
    total = len(results)
    print("\n" + "─" * 55)
    if passed == total:
        print(f"\n{G}{B}✅ All {total} checks passed. System is healthy!{X}\n")
        return 0
    else:
        print(f"\n{R}{B}❌ {total - passed}/{total} checks failed.{X}\n")
        return 1

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:5000")
    args = parser.parse_args()
    sys.exit(run(args.url.rstrip("/")))
