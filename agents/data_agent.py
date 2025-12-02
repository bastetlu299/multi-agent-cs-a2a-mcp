# data_agent.py
# Customer Data Agent exposing A2A endpoints. It calls MCP server tools via HTTP JSON-RPC.

from fastapi import FastAPI, Path
from pydantic import BaseModel
from typing import Any, Dict, Optional, List
import requests

app = FastAPI()

ASSISTANT_ID = "data"
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
# Basic health
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
# Core A2A call model (existing shape)
# ----------------------
class A2ACall(BaseModel):
    tool: str
    arguments: Dict[str, Any] = {}

# ----------------------
# A2A discovery (existing simple card)
# ----------------------
@app.get("/card")
def card():
    return {
        "id": ASSISTANT_ID,
        "name": "Customer Data Agent",
        "endpoints": {
            "call": f"/a2a/{ASSISTANT_ID}/call",
            "tasks": f"/a2a/{ASSISTANT_ID}/tasks"
        }
    }

# ----------------------
# A2A required endpoints with instructor names
# ----------------------
@app.get("/a2a/{assistant_id}/agent_card")
def da_agent_card(assistant_id: str = Path(...)):
    assert assistant_id == ASSISTANT_ID
    return AgentCard(
        id=ASSISTANT_ID,
        name="Customer Data Agent",
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
def da_capabilities(assistant_id: str = Path(...)):
    assert assistant_id == ASSISTANT_ID
    skills = [
        AgentSkill(
            name="get_customer",
            description="Fetch customer by id via MCP",
            inputs={"customer_id": "int"},
            outputs={"customer": "object|null"},
        ),
        AgentSkill(
            name="list_customers",
            description="List customers by optional status and limit via MCP",
            inputs={"status": "str?", "limit": "int"},
            outputs={"customers": "list"},
        ),
        AgentSkill(
            name="update_customer",
            description="Update fields on a customer via MCP",
            inputs={"customer_id": "int", "data": "dict"},
            outputs={"updated": "bool"},
        ),
        AgentSkill(
            name="create_ticket",
            description="Create a ticket via MCP",
            inputs={"customer_id": "int", "issue": "str", "priority": "str"},
            outputs={"ticket_id": "int", "created": "bool"},
        ),
        AgentSkill(
            name="get_customer_history",
            description="List tickets via MCP",
            inputs={"customer_id": "int"},
            outputs={"tickets": "list"},
        ),
    ]
    return AgentCapabilities(a2a=True, tools=[s.name for s in skills], skills=skills)

@app.post("/a2a/{assistant_id}/message")
def da_message(msg: Message, assistant_id: str = Path(...)):
    assert assistant_id == ASSISTANT_ID
    # Minimal demo: if message contains a number, treat as customer id
    import re
    m = re.search(r"\b(\d{1,10})\b", (msg.content or ""))
    if m:
        cid = int(m.group(1))
        return a2a_call(assistant_id, A2ACall(tool="get_customer", arguments={"customer_id": cid}))
    return {"ok": True, "note": "Message received (no auto rule matched)."}

@app.get("/a2a/{assistant_id}/schema")
def da_schema(assistant_id: str = Path(...)):
    assert assistant_id == ASSISTANT_ID
    return {
        "AgentCard": da_agent_card(assistant_id),
        "AgentCapabilities": da_capabilities(assistant_id),
        "ExampleMessage": Message(role="user", content="get customer 1")
    }

# ----------------------
# Existing tasks listing
# ----------------------
@app.get("/a2a/{assistant_id}/tasks")
def a2a_tasks(assistant_id: str = Path(...)):
    assert assistant_id == ASSISTANT_ID
    return {
        "tasks": [
            {"name": "get_customer", "args": {"customer_id": "int"}},
            {"name": "list_customers", "args": {"status": "str?", "limit": "int"}},
            {"name": "update_customer", "args": {"customer_id": "int", "data": "dict"}},
            {"name": "create_ticket", "args": {"customer_id": "int", "issue": "str", "priority": "str"}},
            {"name": "get_customer_history", "args": {"customer_id": "int"}},
        ]
    }

# ----------------------
# A2A call -> MCP tools
# ----------------------
@app.post("/a2a/{assistant_id}/call")
def a2a_call(assistant_id: str, payload: A2ACall):
    assert assistant_id == ASSISTANT_ID
    tool = payload.tool
    args = payload.arguments or {}
    # Forward to MCP tools/call
    body = {"jsonrpc": "2.0", "id": "x", "method": "tools/call", "params": {"tool": tool, "arguments": args}}
    r = requests.post(MCP_URL, json=body, timeout=15)
    if not r.ok:
        return {"ok": False, "error": f"mcp error: {r.status_code}"}
    data = r.json()
    if "error" in data:
        return {"ok": False, "error": data["error"]}
    return data.get("result", {"ok": True})

if __name__ == "__main__":
    import uvicorn
    print("Data agent on http://0.0.0.0:9102")
    uvicorn.run(app, host="0.0.0.0", port=9102)
