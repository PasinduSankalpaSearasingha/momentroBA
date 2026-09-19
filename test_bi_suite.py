import urllib.request
import json
import sys

base = 'http://127.0.0.1:8080'

tests = [
    ('Overview Endpoint', f'{base}/api/bi/overview'),
    ('Agent Status Endpoint', f'{base}/api/bi/agent-status'),
    ('Analytics Endpoint', f'{base}/api/analytics'),
    ('Leads List Endpoint', f'{base}/api/leads'),
    ('Lead 1 Detail Endpoint', f'{base}/api/leads/1'),
    ('Lead 2 Detail Endpoint', f'{base}/api/leads/2'),
    ('BI Command Center HTML', f'{base}/bi-automation'),
    ('BI Alias Route HTML', f'{base}/bi'),
    ('Leads Page HTML', f'{base}/leads'),
    ('Company Report HTML', f'{base}/company-report'),
    ('Dashboard HTML', f'{base}/dashboard'),
]

print("=" * 60)
print("  MOMENTRO BI VERIFICATION SUITE")
print("=" * 60)

all_passed = True
for name, url in tests:
    try:
        res = urllib.request.urlopen(url)
        print(f"PASS | {name:25} | Status: {res.status}")
    except Exception as e:
        print(f"FAIL | {name:25} | Error: {e}")
        all_passed = False

# Test Auto-Pilot Run
try:
    req = urllib.request.Request(
        f'{base}/api/bi/auto-pilot/run',
        data=json.dumps({'lead_id': 2}).encode(),
        headers={'Content-Type': 'application/json'}
    )
    res = urllib.request.urlopen(req)
    data = json.loads(res.read().decode('utf-8'))
    success = data.get('success')
    steps = len(data.get('step_logs', []))
    print(f"PASS | Auto-Pilot Run API       | Success={success}, Steps={steps}")
except Exception as e:
    print(f"FAIL | Auto-Pilot Run API       | Error: {e}")
    all_passed = False

# Test Status update endpoint
try:
    req = urllib.request.Request(
        f'{base}/api/leads/2/status',
        data=json.dumps({'status': 'Approved'}).encode(),
        headers={'Content-Type': 'application/json'}
    )
    res = urllib.request.urlopen(req)
    data = json.loads(res.read().decode('utf-8'))
    print(f"PASS | Update Lead Status API   | Success={data.get('success')}, Status={data.get('new_status')}")
except Exception as e:
    print(f"FAIL | Update Lead Status API   | Error: {e}")
    all_passed = False

print("=" * 60)
if all_passed:
    print("ALL TESTS PASSED SUCCESSFULLY! BI COMMAND CENTER READY.")
else:
    print("SOME TESTS FAILED.")
print("=" * 60)
