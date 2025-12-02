# mcp_server.py
# FastAPI JSON-RPC MCP server exposing tools/list and tools/call, plus health check.
# Uses the SQLite DB created by your instructor's database_setup.py.

import sqlite3
from datetime import datetime
from fastapi import FastAPI
from pydantic import BaseModel
from typing import Any, Dict, Optional, Union

DB_PATH = "support.db"

app = FastAPI()

# ----------------------
# Healthz for readiness
# ----------------------
@app.get("/healthz")
def healthz():
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT 1")
        conn.close()
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}

# ----------------------
# DB helpers
# ----------------------
def connect_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def row_to_dict(row):
    if row is None:
        return None
    return dict(row)

def rows_to_list(rows):
    return [dict(r) for r in rows]

# ----------------------
# JSON-RPC model
# ----------------------
class JsonRpcRequest(BaseModel):
    jsonrpc: str = "2.0"
    method: str
    params: Optional[Dict[str, Any]] = None
    id: Optional[Union[str, int]] = None

# ----------------------
# MCP tools (pure functions)
# ----------------------
def mcp_get_customer(customer_id: int):
    conn = connect_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM customers WHERE id = ?", (customer_id,))
    row = cur.fetchone()
    conn.close()
    return {"customer": row_to_dict(row)}

def mcp_list_customers(status: Optional[str], limit: int):
    conn = connect_db()
    cur = conn.cursor()
    if status:
        cur.execute("SELECT * FROM customers WHERE status = ? LIMIT ?", (status, limit))
    else:
        cur.execute("SELECT * FROM customers LIMIT ?", (limit,))
    rows = cur.fetchall()
    conn.close()
    return {"customers": rows_to_list(rows)}

def mcp_update_customer(customer_id: int, data: Dict[str, Any]):
    if not data:
        return {"updated": False, "error": "No fields to update"}
    # Build update dynamically and always bump updated_at
    fields = []
    values = []
    for k, v in data.items():
        fields.append(f"{k} = ?")
        values.append(v)
    fields.append("updated_at = ?")
    values.append(datetime.utcnow())  # UTC timestamp
    values.append(customer_id)

    conn = connect_db()
    cur = conn.cursor()
    cur.execute(f"UPDATE customers SET {', '.join(fields)} WHERE id = ?", values)
    conn.commit()
    changed = cur.rowcount
    conn.close()
    return {"updated": changed > 0}

def mcp_create_ticket(customer_id: int, issue: str, priority: str):
    conn = connect_db()
    cur = conn.cursor()
    now = datetime.utcnow()
    cur.execute(
        """
        INSERT INTO tickets (customer_id, issue, status, priority, created_at)
        VALUES (?, ?, 'open', ?, ?)
        """,
        (customer_id, issue, priority, now),
    )
    ticket_id = cur.lastrowid
    conn.commit()
    conn.close()
    return {"ticket_id": ticket_id, "created": True}

def mcp_get_customer_history(customer_id: int):
    conn = connect_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM tickets WHERE customer_id = ? ORDER BY created_at DESC", (customer_id,))
    rows = cur.fetchall()
    conn.close()
    return {"tickets": rows_to_list(rows)}

# ----------------------
# JSON-RPC dispatcher
# ----------------------
@app.post("/mcp")
async def mcp_handler(req: JsonRpcRequest):
    method = req.method
    params = req.params or {}

    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req.id,
            "result": {
                "tools": [
                    {
                        "name": "get_customer",
                        "description": "Get a single customer by ID",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"customer_id": {"type": "integer"}},
                            "required": ["customer_id"],
                        },
                    },
                    {
                        "name": "list_customers",
                        "description": "List customers (optional status, limit)",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "status": {"type": ["string", "null"]},
                                "limit": {"type": "integer"},
                            },
                            "required": ["limit"],
                        },
                    },
                    {
                        "name": "update_customer",
                        "description": "Update fields on a customer",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "customer_id": {"type": "integer"},
                                "data": {"type": "object"},
                            },
                            "required": ["customer_id", "data"],
                        },
                    },
                    {
                        "name": "get_customer_history",
                        "description": "List tickets for a customer",
                        "inputSchema": {
                            "type": "object",
                            "properties": {"customer_id": {"type": "integer"}},
                            "required": ["customer_id"],
                        },
                    },
                    {
                        "name": "create_ticket",
                        "description": "Create a support ticket",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "customer_id": {"type": "integer"},
                                "issue": {"type": "string"},
                                "priority": {"type": "string"},
                            },
                            "required": ["customer_id", "issue", "priority"],
                        },
                    },
                ]
            }
        }

    if method == "tools/call":
        tool = (params.get("tool") or params.get("name") or "").strip()
        args = params.get("arguments") or params.get("params") or {}
        if not tool:
            return {
                "jsonrpc": "2.0",
                "id": req.id,
                "error": {"code": -32602, "message": "Tool name not provided"},
            }
        try:
            if tool == "get_customer":
                res = mcp_get_customer(int(args["customer_id"]))
            elif tool == "list_customers":
                res = mcp_list_customers(args.get("status"), int(args.get("limit", 100)))
            elif tool == "update_customer":
                res = mcp_update_customer(int(args["customer_id"]), dict(args.get("data", {})))
            elif tool == "create_ticket":
                res = mcp_create_ticket(int(args["customer_id"]), str(args["issue"]), str(args.get("priority", "medium")))
            elif tool == "get_customer_history":
                res = mcp_get_customer_history(int(args["customer_id"]))
            else:
                return {
                    "jsonrpc": "2.0",
                    "id": req.id,
                    "error": {"code": -32601, "message": f"Unknown tool: {tool}"},
                }
            return {"jsonrpc": "2.0", "id": req.id, "result": res}
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": req.id,
                "error": {"code": -32001, "message": f"Tool execution error: {e}"},
            }

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req.id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "CustomerMCP", "version": "1.0.0"},
            },
        }

    if method == "notifications/initialized":
        return {"jsonrpc": "2.0", "id": req.id, "result": {"ok": True}}

    return {
        "jsonrpc": "2.0",
        "id": req.id,
        "error": {"code": -32601, "message": f"Unknown method: {method}"},
    }

if __name__ == "__main__":
    import uvicorn
    print("MCP JSON-RPC server on http://0.0.0.0:9010")
    uvicorn.run(app, host="0.0.0.0", port=9010)
