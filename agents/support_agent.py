# support_agent.py
# Support Agent with A2A interface. It drafts suggestions and uses MCP for tickets/history.

from fastapi import FastAPI, Path
from pydantic import BaseModel
from typing import Any, Dict, Optional, List
import requests

app = FastAPI()

ASSISTANT_ID = "support"
MCP_URL = "http://127.0.0.1:9010/mcp"
HEALTH_URL = "http://127.0.0.1:9010/healthz"

# ----------------------
# A2A wrapper models (names required by instructor)
# ----------------------
class AgentProvider(BaseModel):
    name: str
    sdk: str
    homepage: Optional[str] = None

class AgentSkill(BaseModel):
    name: str
    description: str
    inputs: Dict[str, str]
    outputs: Dict[str, str]

class AgentCapabilities(BaseModel):
    a2a: bool
    tools: List[str]
    skills: List[AgentSkill]

class AgentCard(BaseModel):
    id: str
    name: str
    version: str = "1.0"
    provider: AgentProvider
    endpoints: Dict[str, str]

class Message(BaseModel):
    role: str
    content: str
    meta: Optional[Dict[str, Any]] = None

# ----------------------
# Health
# ----------------------
@app.get("/healthz")
def healthz():
    try:
        r = requests.get(HEALTH_URL, timeout=5)
        ok = r.ok and r.json().get("ok")
        return {"ok": bool(ok)}
    except Exception as e:
        return {"ok": False, "error": str(e)}

# ----------------------
# Core call model
# ----------------------
class A2ACall(BaseModel):
    tool: str
    arguments: Dict[str, Any] = {}

# ----------------------
# Simple discovery
# ----------------------
@app.get("/card")
def card():
    return {
        "id": ASSISTANT_ID,
        "name": "Support Agent",
        "endpoints": {
            "call": f"/a2a/{ASSISTANT_ID}/call",
            "tasks": f"/a2a/{ASSISTANT_ID}/tasks"
        }
    }

# ----------------------
# Instructor-named A2A endpoints
# ----------------------
@app.get("/a2a/{assistant_id}/agent_card")
def sa_agent_card(assistant_id: str = Path(...)):
    assert assistant_id == ASSISTANT_ID
    return AgentCard(
        id=ASSISTANT_ID,
        name="Support Agent",
        provider=AgentProvider(name="Custom FastAPI", sdk="A2A JSON-RPC over HTTP"),
        endpoints={
            "card": "/a2a/{assistant_id}/agent_card",
            "capabilities": "/a2a/{assistant_id}/capabilities",
            "tasks": "/a2a/{assistant_id}/tasks",
            "call": "/a2a/{assistant_id}/call",
            "message": "/a2a/{assistant_id}/message",
        }
    )

@app.get("/a2a/{assistant_id}/capabilities")
def sa_capabilities(assistant_id: str = Path(...)):
    assert assistant_id == ASSISTANT_ID
    skills = [
        AgentSkill(
            name="simple_support_reply",
            description="Return a short textual reply based on the issue context",
            inputs={"text": "str", "customer_id": "int?"},
            outputs={"text": "str", "intent": "str"},
        ),
        AgentSkill(
            name="suggest_resolution",
            description="Draft a support suggestion; may consult Data Agent externally",
            inputs={"text": "str", "customer_id": "int?"},
            outputs={"suggestion": "str", "context": "dict", "intent": "str"},
        ),
        AgentSkill(
            name="create_ticket",
            description="Create a ticket through MCP",
            inputs={"customer_id": "int", "issue": "str", "priority": "str"},
            outputs={"ticket_id": "int", "created": "bool"},
        ),
        AgentSkill(
            name="tickets_report_for_customers",
            description="Aggregate tickets for a list of customers; optional priority filter",
            inputs={"customer_ids": "list[int]", "priority": "str?"},
            outputs={"report": "list", "filter_priority": "str?"},
        ),
    ]
    return AgentCapabilities(a2a=True, tools=[s.name for s in skills], skills=skills)

@app.post("/a2a/{assistant_id}/message")
def sa_message(msg: Message, assistant_id: str = Path(...)):
    assert assistant_id == ASSISTANT_ID
    t = (msg.content or "").lower()
    if "refund" in t or "charged twice" in t:
        return a2a_call(assistant_id, A2ACall(tool="suggest_resolution", arguments={"text": msg.content}))
    return {"ok": True, "note": "Message received (no auto rule matched)."}

@app.get("/a2a/{assistant_id}/schema")
def sa_schema(assistant_id: str = Path(...)):
    assert assistant_id == ASSISTANT_ID
    return {
        "AgentCard": sa_agent_card(assistant_id),
        "AgentCapabilities": sa_capabilities(assistant_id),
        "ExampleMessage": Message(role="user", content="I've been charged twice, please refund")
    }

# ----------------------
# Tasks list
# ----------------------
@app.get("/a2a/{assistant_id}/tasks")
def a2a_tasks(assistant_id: str = Path(...)):
    assert assistant_id == ASSISTANT_ID
    return {
        "tasks": [
            {"name": "simple_support_reply", "args": {"text": "str", "customer_id": "int?"}},
            {"name": "suggest_resolution", "args": {"text": "str", "customer_id": "int?"}},
            {"name": "create_ticket", "args": {"customer_id": "int", "issue": "str", "priority": "str"}},
            {"name": "tickets_report_for_customers", "args": {"customer_ids": "list[int]", "priority": "str?"}},
        ]
    }

# ----------------------
# Tool implementations (uses MCP)
# ----------------------
def mcp_call(tool: str, arguments: Dict[str, Any]):
    body = {"jsonrpc": "2.0", "id": "x", "method": "tools/call", "params": {"tool": tool, "arguments": arguments}}
    r = requests.post(MCP_URL, json=body, timeout=15)
    r.raise_for_status()
    data = r.json()
    if "error" in data:
        raise RuntimeError(data["error"])
    return data["result"]

def _guess_intent(text: str) -> str:
    t = (text or "").lower()
    if "refund" in t or "charge" in t or "billing" in t:
        return "billing"
    if "delay" in t or "delivery" in t or "shipping" in t:
        return "shipping"
    return "general"

def tool_suggest_resolution(text: str, customer_id: Optional[int] = None):
    context = {}
    if customer_id is not None:
        try:
            hist = mcp_call("get_customer_history", {"customer_id": customer_id})
            context["history"] = hist
        except Exception:
            context["history"] = {"error": "history unavailable"}
    intent = _guess_intent(text)
    suggestion = (
        "I understand your issue. "
        "For billing/refund, we can initiate a refund and confirm the payment record. "
        "If shipping, we open a tracking case; for general issues, we provide step-by-step guidance."
    )
    return {"suggestion": suggestion, "context": context, "intent": intent}

def tool_create_ticket(customer_id: int, issue: str, priority: str):
    return mcp_call("create_ticket", {"customer_id": customer_id, "issue": issue, "priority": priority})

def tool_tickets_report_for_customers(customer_ids: List[int], priority: Optional[str] = None):
    report = []
    for cid in customer_ids:
        hist = mcp_call("get_customer_history", {"customer_id": cid})
        tickets = hist.get("tickets", [])
        if priority:
            tickets = [t for t in tickets if str(t.get("priority")).lower() == priority.lower()]
        report.append({"customer_id": cid, "tickets": tickets})
    return {"report": report, "filter_priority": priority}

def tool_simple_support_reply(text: str, customer_id: Optional[int] = None):
    res = tool_suggest_resolution(text, customer_id)
    reply = res.get("suggestion") or (
        "Thanks for contacting support. We'll investigate and follow up shortly."
    )
    return {"text": reply, "intent": res.get("intent", "general"), "context": res.get("context", {})}

# ----------------------
# A2A call dispatcher
# ----------------------
@app.post("/a2a/{assistant_id}/call")
def a2a_call(assistant_id: str, payload: A2ACall):
    assert assistant_id == ASSISTANT_ID
    tool = payload.tool
    args = payload.arguments or {}
    if tool == "suggest_resolution":
        return tool_suggest_resolution(args.get("text", ""), args.get("customer_id"))
    if tool == "simple_support_reply":
        return tool_simple_support_reply(args.get("text", ""), args.get("customer_id"))
    if tool == "create_ticket":
        return tool_create_ticket(int(args["customer_id"]), str(args["issue"]), str(args.get("priority", "medium")))
    if tool == "tickets_report_for_customers":
        return tool_tickets_report_for_customers(list(args.get("customer_ids", [])), args.get("priority"))
    return {"ok": False, "error": f"Unknown tool: {tool}"}

if __name__ == "__main__":
    import uvicorn
    print("Support agent on http://0.0.0.0:9103")
    uvicorn.run(app, host="0.0.0.0", port=9103)
