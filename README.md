# Multi-Agent Customer Service with MCP + A2A (LangGraph demos included)

A complete, reproducible reference implementation of:
- **MCP JSON-RPC server** exposing database tools via `tools/list` and `tools/call`
- Three **independent A2A agents** (Router / Data / Support), each with `/card` and `/a2a/call`
- **End-to-end tests** covering 5 assignment scenarios
- **LangGraph demos** for sequential and router-based multi-agent patterns
- MCP Inspector screenshots & instructions

---

## Repo Layout

mcp-project/
├─ mcp_server.py # MCP JSON-RPC server (tools/list, tools/call, /healthz)
├─ database_setup.py # Creates and seeds SQLite DB (support.db)
├─ agents/
│ ├─ router_agent.py # /card, /a2a/call (port 9201)
│ ├─ data_agent.py # /card, /a2a/call (port 9102) - calls MCP tools
│ └─ support_agent.py # /card, /a2a/call (port 9103)
├─ demos/
│ ├─ sequential_demo.py # LangGraph sequential pattern demo
│ └─ router_demo.py # LangGraph router pattern demo
├─ tests/
│ └─ run_tests.py # Runs 5 assignment scenarios and prints logs/results
├─ docs/
│ ├─ inspector-tools-list.png # MCP Inspector screenshot (tools/list)
│ ├─ inspector-tools-call.png # MCP Inspector screenshot (tools/call)
│ └─ architecture.png # High-level diagram (optional)
├─ .env.example # Example env/ports (copy to .env if needed)
├─ .gitignore
├─ requirements.txt
├─ run_all.sh # Start MCP + 3 agents (or start each in separate shells)
└─ README.md

yaml
Copy code

---

## Requirements

- **Python 3.10+**
- macOS / Linux / Windows (WSL recommended on Windows)
- (Optional) **MCP Inspector** (Node.js required): `npx @modelcontextprotocol/inspector`

---

## Quick Start (100% reproducible)

### 1) Create & activate a virtual env

```bash
python3 -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
2) Initialize the database
bash
Copy code
python database_setup.py
# This creates/overwrites support.db with seed customers + tickets
3) Start all services (recommended)
bash
Copy code
bash run_all.sh
It launches:

MCP server on http://127.0.0.1:9010

Data agent on http://127.0.0.1:9102

Support agent on http://127.0.0.1:9103

Router agent on http://127.0.0.1:9201

Prefer separate terminals? Start each with:

bash
Copy code
uvicorn mcp_server:app --host 0.0.0.0 --port 9010
uvicorn agents.data_agent:app --host 0.0.0.0 --port 9102
uvicorn agents.support_agent:app --host 0.0.0.0 --port 9103
uvicorn agents.router_agent:app --host 0.0.0.0 --port 9201
Sanity Checks
MCP health
bash
Copy code
curl -s http://127.0.0.1:9010/healthz
# {"ok": true}
MCP tools/list (JSON-RPC)
bash
Copy code
curl -s -X POST http://127.0.0.1:9010/mcp \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":"x","method":"tools/list"}' | jq .
You should see tool entries with inputSchema for:
get_customer, list_customers, update_customer,
get_customer_history, create_ticket.

MCP tools/call example
bash
Copy code
curl -s -X POST http://127.0.0.1:9010/mcp \
  -H 'Content-Type: application/json' \
  -d '{
        "jsonrpc":"2.0",
        "id":"call1",
        "method":"tools/call",
        "params":{
          "tool":"get_customer",
          "arguments":{"customer_id":5}
        }
      }' | jq .
A2A Agent Sanity Checks
Each agent exposes:

GET /card → agent “card” (id, name, capabilities)

POST /a2a/call → JSON-RPC-like call:

json
Copy code
{ "tool": "<name>", "arguments": { ... } }
Data Agent
bash
Copy code
curl -s http://127.0.0.1:9102/card | jq .
curl -s -X POST http://127.0.0.1:9102/a2a/call \
  -H 'Content-Type: application/json' \
  -d '{"tool":"get_customer","arguments":{"customer_id":5}}' | jq .
Support Agent
bash
Copy code
curl -s http://127.0.0.1:9103/card | jq .
curl -s -X POST http://127.0.0.1:9103/a2a/call \
  -H 'Content-Type: application/json' \
  -d '{"tool":"create_ticket","arguments":{"customer_id":1,"issue":"cannot login","priority":"high"}}' | jq .
Router Agent
bash
Copy code
curl -s http://127.0.0.1:9201/card | jq .
curl -s -X POST http://127.0.0.1:9201/a2a/call \
  -H 'Content-Type: application/json' \
  -d '{"task":"route","text":"create ticket for customer 1: cannot pay",
       "args":{"customer_id":1,"issue":"cannot pay","priority":"high"}}' | jq .
MCP Inspector (independent client)
Keep MCP server running on :9010.

In a new terminal:

bash
Copy code
npx @modelcontextprotocol/inspector
In the Inspector UI:

Transport: Streamable HTTP

URL: http://127.0.0.1:9010/mcp

Click Connect → Initialize

Click Tools → you should see the tool list

Try tools/call with:

json
Copy code
{
  "tool": "get_customer",
  "arguments": { "customer_id": 5 }
}
Take screenshots and save into docs/:

docs/inspector-tools-list.png

docs/inspector-tools-call.png

If the Inspector complains about missing inputSchema, ensure your tools/list response includes inputSchema objects (this repo does).

Run End-to-End Tests (5 scenarios)
bash
Copy code
python tests/run_tests.py
Expected: prints five blocks (Simple, Coordinated, Complex, Escalation, Multi-Intent) with Route, Logs, and a Final answer.
Example (abridged):

makefile
Copy code
================================================================================
TEST: Simple Query
--------------------------------------------------------------------------------
Query: Get customer information for ID 5
Scenario: data
Route: router -> data
Logs:
  - Router classified as DATA
  - Data Agent used MCP tools
Final answer:
 { "type": "get_customer", "customer_id": 5, "customer": {...} }
LangGraph Demos (optional, for the “What You Will Build” part)
Sequential pattern:

bash
Copy code
python demos/sequential_demo.py
Router pattern:

bash
Copy code
python demos/router_demo.py
Both demos require OPENAI_API_KEY if they call an LLM. You can run them with simple mock tool logic if you prefer not to invoke an external model.

Troubleshooting
Port already in use

Kill the old process or change the port.

bash
Copy code
lsof -i :9010
kill -9 <PID>
MCP Inspector “422 Unprocessable Entity”

Your JSON-RPC must include "jsonrpc":"2.0", a string id, and the correct method.

For tools/list, return inputSchema for every tool.

Read timeout / connection refused

Check the order: start MCP first, then Data, Support, then Router.

Confirm /healthz returns {"ok":true}.

DB got messy while testing

Recreate it:

bash
Copy code
rm -f support.db
python database_setup.py
Infinite loops / long waits

Agents include max-iteration guards and timeouts. If you changed them, revert to defaults.

Environment & Versions
See requirements.txt. If you change versions, ensure the project still passes:

tools/list shows inputSchema

tools/call works for all tools

/card & /a2a/call work on all agents

tests/run_tests.py prints 5 passing scenarios


