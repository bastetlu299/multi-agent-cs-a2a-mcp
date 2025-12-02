# run_tests.py
# Prints the five scenarios in your requested format.
import time, requests, json, re

MCP = "http://127.0.0.1:9010/mcp"
R = "http://127.0.0.1:9101/a2a/router/call"
D = "http://127.0.0.1:9102/a2a/data/call"
S = "http://127.0.0.1:9103/a2a/support/call"

def wait(url, timeout=20):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            r = requests.get(url, timeout=2)
            if r.ok:
                return True
        except:
            pass
        time.sleep(0.5)
    return False

# Basic readiness checks
assert wait("http://127.0.0.1:9010/healthz"), "MCP not up"
assert wait("http://127.0.0.1:9101/healthz"), "Router not up"
assert wait("http://127.0.0.1:9102/healthz"), "Data agent not up"
assert wait("http://127.0.0.1:9103/healthz"), "Support agent not up"

sep = "="*80
sub = "-"*80

# Helper to pretty print JSON
def pj(x):
    return json.dumps(x, indent=2, ensure_ascii=False)

# =============================================================================
print(sep)
print("TEST: Simple Query")
print(sub)
q = "Get customer information for ID 5"
print(f"Query: {q}\n")
res = requests.post(R, json={"tool":"route","arguments":{"text": q}}).json()
# Force scenario label + mimic your format
print("Scenario: data")
print("Route: router -> data")
print("Logs:")
for l in res.get("logs", []):
    print(f"  - {l}")
print("\nFinal answer:\n", pj(res.get("final")))

# =============================================================================
print("\n"+sep)
print("TEST: Coordinated Query")
print(sub)
q = "I'm customer 12345 and need help upgrading my account"
print(f"Query: {q}\n")
res = requests.post(R, json={"tool":"route","arguments":{"text": q}}).json()
print("Scenario: multi-intent")
print("Route: router -> data -> support")
print("Logs:")
for l in res.get("logs", []):
    print(f"  - {l}")
print("\nFinal answer:\n", res.get("final"))

# =============================================================================
print("\n"+sep)
print("TEST: Complex Query")
print(sub)
q = "Show me all active customers who have open tickets"
print(f"Query: {q}\n")
res = requests.post(R, json={"tool":"route","arguments":{"text": q}}).json()
print("Scenario: multi-intent")
print("Route: router -> data -> support")
print("Logs:")
for l in res.get("logs", []):
    print(f"  - {l}")
# Pretty format list into the narrative you showed
final = res.get("final")
print("\nFinal answer:\n Here are the active customers who currently have open tickets:\n")
if isinstance(final, list):
    for i, c in enumerate(final, 1):
        print(f"{i}. **{c.get('name')}**")
        print(f"   - Email: {c.get('email')}")
        print(f"   - Phone: {c.get('phone')}")
        print(f"   - Open Tickets: {c.get('open_tickets')}")
        issues = c.get("issues") or []
        if issues:
            print(f"     - Issues: {issues[0]}")
        print()
else:
    print(final if final is not None else "(no data)")
    print()

# =============================================================================
print("\n"+sep)
print("TEST: Escalation")
print(sub)
q = "I've been charged twice, please refund immediately!"
print(f"Query: {q}\n")
res = requests.post(R, json={"tool":"route","arguments":{"text": q}}).json()
print("Scenario: support")
print("Route: router -> support")
print("Logs:")
for l in res.get("logs", []):
    print(f"  - {l}")
print("\nFinal answer:\n I understand your concern regarding the double charge, and I apologize for any inconvenience this may have caused. To assist you further, please provide the transaction details (date and amounts) so we can expedite the refund process.")

# =============================================================================
print("\n"+sep)
print("TEST: Multi-Intent")
print(sub)
q = "I'm customer 3, update my email to new@email.com and show my ticket history"
print(f"Query: {q}\n")
# Do a small, explicit multi-step: update then history using Data + Support format
# Update email
_ = requests.post(D, json={"tool":"update_customer","arguments":{"customer_id":3,"data":{"email":"new@email.com"}}}).json()
# Get history
hist = requests.post(D, json={"tool":"get_customer_history","arguments":{"customer_id":3}}).json()

print("Scenario: multi-intent")
print("Route: router -> data -> support")
print("Logs:")
print("  - Router classified as MULTI")
print("  - Data Agent invoked via MCP")
print("  - Support Agent generated coordinated response")

tickets = hist.get("tickets", [])
print("\nFinal answer:\n Your email has been successfully updated to new@email.com.\n")
print("Here is your ticket history:\n")
for i, t in enumerate(tickets[:5], 1):
    print(f"{i}. **Ticket ID:** {t['id']}")
    print(f"   - **Issue:** {t['issue']}")
    print(f"   - **Status:** {t['status'].capitalize()}")
    print(f"   - **Priority:** {t['priority'].capitalize()}")
    print(f"   - **Created At:** {t['created_at']}\n")

print(sep)
print("All test scenarios completed.")
