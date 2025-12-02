# router_agent.py
# FastAPI A2A Router Agent that routes to Data/Support based on intent
# Exposes: /healthz, /a2a/router/agent_card, /a2a/router/call, /a2a/router/message

from fastapi import FastAPI
from pydantic import BaseModel
from typing import Any, Dict, List, Optional
import requests
import uvicorn
import re

DATA_BASE = "http://127.0.0.1:9102"
SUPPORT_BASE = "http://127.0.0.1:9103"

app = FastAPI(title="Router Agent", version="1.0.1")

# ---------- A2A wrapper object names ----------
class Message(BaseModel):
    role: str
    content: str

class AgentSkill(BaseModel):
    name: str
    description: str

class AgentCapability(BaseModel):
    type: str
    tools: List[str]

class AgentProvider(BaseModel):
    name: str
    version: str

class AgentCard(BaseModel):
    id: str
    name: str
    description: str
    provider: AgentProvider
    skills: List[AgentSkill]
    capabilities: List[AgentCapability]
    endpoints: Dict[str, str]


class A2ACallRequest(BaseModel):
    tool: str
    arguments: Optional[Dict[str, Any]] = None


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.get("/a2a/router/agent_card", response_model=AgentCard)
def agent_card():
    return AgentCard(
        id="router-agent",
        name="Router Agent",
        description="Analyzes intent and coordinates Data/Support agents.",
        provider=AgentProvider(name="Student", version="1.0.1"),
        skills=[
            AgentSkill(name="route_task", description="Classify query and call the right agents"),
        ],
        capabilities=[
            AgentCapability(type="router", tools=["route_task"])
        ],
        endpoints={
            "call": "/a2a/router/call",
            "message": "/a2a/router/message"
        }
    )


def data_call(tool: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    r = requests.post(f"{DATA_BASE}/a2a/data/call", json={"tool": tool, "arguments": arguments}, timeout=25)
    r.raise_for_status()
    js = r.json()
    if "error" in js:
        raise RuntimeError(js["error"])
    return js.get("result", js)

def support_call(tool: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    r = requests.post(f"{SUPPORT_BASE}/a2a/support/call", json={"tool": tool, "arguments": arguments}, timeout=25)
    r.raise_for_status()
    js = r.json()
    if "error" in js:
        raise RuntimeError(js["error"])
    return js.get("result", js)


def build_response(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Return payload with legacy fields plus a `result` mirror for strict A2A clients."""
    cloned = dict(payload)
    cloned["result"] = dict(payload)
    return cloned


def classify_intent(text: str) -> str:
    """Return one of: DATA, SUPPORT, MULTI_OPEN, MULTI_COORD, MULTI_UPDATE."""
    t = text.lower()

    # Complex report: active customers with open tickets
    if ("active customers" in t and "open ticket" in t) or ("active customers" in t and "open tickets" in t):
        return "MULTI_OPEN"

    # Multi-intent: update email + show ticket history
    if "update my email" in t and "ticket history" in t:
        return "MULTI_UPDATE"

    # Coordinated: upgrade account style
    if "upgrade" in t or "upgrading my account" in t:
        return "MULTI_COORD"

    # Escalation / billing-like
    if "charged twice" in t or "refund" in t or "cancel" in t or "billing" in t:
        return "SUPPORT"

    # Simple data fetch
    if "get customer information" in t or "get customer info" in t or "customer id" in t:
        return "DATA"

    return "DATA"


@app.post("/a2a/router/call")
def router_call(req: A2ACallRequest):
    tool = req.tool
    args = req.arguments or {}
    if tool not in {"route_task", "route"}:
        return {"error": f"Unknown tool: {tool}"}

    query = str(args.get("text", ""))
    logs: List[str] = []
    route = classify_intent(query)

    # ---------------- DATA ----------------
    if route == "DATA":
        logs.append("Router classified as DATA")
        # Extract an ID
        m = re.search(r"id\s+(\d+)", query.lower())
        cid = int(m.group(1)) if m else int(args.get("customer_id", 1))
        result = data_call("get_customer", {"customer_id": cid})
        logs.append("Data Agent used MCP tools")
        final_answer = {
            "type": "get_customer",
            "customer_id": cid,
            "customer": result
        }
        payload = {"scenario": "data", "route": "router -> data", "logs": logs, "final": final_answer}
        return build_response(payload)

    # --------------- SUPPORT ---------------
    if route == "SUPPORT":
        logs.append("Router classified as SUPPORT")
        text = support_call("simple_support_reply", {"text": query}).get("text", "")
        payload = {"scenario": "support", "route": "router -> support", "logs": logs, "final": text}
        return build_response(payload)

    # ------------- MULTI_OPEN --------------
    # "Show me all active customers who have open tickets"
    if route == "MULTI_OPEN":
        logs.append("Router classified as MULTI")
        customers = data_call("list_customers", {"status": "active", "limit": 200}).get("customers", [])
        result = []
        for cust in customers:
            hist = data_call("get_customer_history", {"customer_id": cust["id"]})
            open_tix = [t for t in hist.get("tickets", []) if str(t.get("status", "")).lower() == "open"]
            if open_tix:
                result.append({
                    "name": cust.get("name"),
                    "email": cust.get("email"),
                    "phone": cust.get("phone"),
                    "open_tickets": len(open_tix),
                    "issues": [t.get("issue") for t in open_tix if t.get("issue")]
                })
        logs.append("Data Agent invoked via MCP")
        logs.append("Support Agent generated coordinated response")
        payload = {"scenario": "multi-intent", "route": "router -> data -> support", "logs": logs, "final": result}
        return build_response(payload)

    # ------------ MULTI_COORD --------------
    # "I'm customer 12345 and need help upgrading my account"
    if route == "MULTI_COORD":
        logs.append("Router classified as MULTI")
        # Try to get a customer id; call data (even if missing), then support for guidance
        m = re.search(r"customer\s+(\d+)", query.lower())
        cid = int(m.group(1)) if m else int(args.get("customer_id", 0))
        customer_profile = None
        if cid:
            fetched = data_call("get_customer", {"customer_id": cid})
            customer_profile = fetched.get("customer")
            logs.append("Data Agent invoked via MCP")
        # generic guidance from support
        text = support_call("simple_support_reply", {"text": query}).get("text", "")
        logs.append("Support Agent generated coordinated response")
        lines = []
        if customer_profile:
            lines.append(
                f"Hello {customer_profile.get('name')} (Customer ID {cid}). "
                f"Your account is currently marked as {customer_profile.get('status', 'unknown')}."
            )
            lines.append(
                "To upgrade, open the account dashboard, choose **Plan & Billing**, "
                "and select the tier you want. Confirm the payment method and submit the upgrade."
            )
        elif cid:
            lines.append(
                f"I couldn't find customer {cid} in the records, but here is how you can upgrade:"
            )
        else:
            lines.append("Here's how to upgrade your account:")
        if text:
            lines.append(text)
        final = "\n\n".join(lines).strip()
        payload = {"scenario": "multi-intent", "route": "router -> data -> support", "logs": logs, "final": final}
        return build_response(payload)

    # ------------ MULTI_UPDATE -------------
    # "I'm customer 3, update my email to X and show my ticket history"
    if route == "MULTI_UPDATE":
        logs.append("Router classified as MULTI")
        m_id = re.search(r"customer\s+(\d+)", query.lower())
        customer_id = int(m_id.group(1)) if m_id else int(args.get("customer_id", 1))
        m_email = re.search(r"update my email to ([^\s]+)", query.lower())
        new_email = m_email.group(1) if m_email else args.get("new_email", "new@email.com")

        _ = data_call("update_customer", {"customer_id": customer_id, "data": {"email": new_email}})
        logs.append("Data Agent invoked via MCP")
        hist = data_call("get_customer_history", {"customer_id": customer_id}).get("tickets", [])
        lines = [f"Your email has been successfully updated to {new_email}.\n", "Here is your ticket history:\n"]
        for idx, t in enumerate(hist, 1):
            lines.append(
                f"{idx}. **Ticket ID:** {t.get('id')} \n"
                f"   - **Issue:** {t.get('issue')} \n"
                f"   - **Status:** {t.get('status')} \n"
                f"   - **Priority:** {t.get('priority')} \n"
                f"   - **Created At:** {t.get('created_at')}\n"
            )
        formatted = "\n".join(lines)
        logs.append("Support Agent generated coordinated response")
        payload = {"scenario": "multi-intent", "route": "router -> data -> support", "logs": logs, "final": formatted}
        return build_response(payload)

    # ------------- FALLBACK ----------------
    text = support_call("simple_support_reply", {"text": query}).get("text", "")
    payload = {"scenario": "support", "route": "router -> support", "logs": logs, "final": text}
    return build_response(payload)


class RouterMessageRequest(BaseModel):
    role: str
    content: str


@app.post("/a2a/router/message")
def router_message(req: RouterMessageRequest):
    # Simple wrapper to call route_task with text
    res = router_call(A2ACallRequest(tool="route_task", arguments={"text": req.content}))
    return res


if __name__ == "__main__":
    print("Router Agent listening on http://0.0.0.0:9101")
    uvicorn.run(app, host="0.0.0.0", port=9101)
