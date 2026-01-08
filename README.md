# Multi-Agent Customer Service Platform (MCP + A2A)

A production-style, reproducible reference project that demonstrates how to build a **multi-agent customer service system** with:

- **MCP JSON-RPC server** that exposes database tools (`tools/list`, `tools/call`)
- **Three independent A2A agents** (Router, Data, Support) with `/card` and `/a2a/call`
- **End-to-end tests** covering five assignment scenarios
- **LangGraph demos** for sequential and router-based multi-agent patterns
- **MCP Inspector** instructions and screenshots

---

## Why this project

This repository is designed to be **recruiter-friendly** and easy to evaluate. It provides:

- A **clear architecture** for agent orchestration and tool calls
- **Readable, runnable** Python services and test suites
- **Reproducible results** with one-command startup and deterministic fixtures

---

## Project structure

```
mcp-project/
├─ mcp_server.py                 # MCP JSON-RPC server (tools/list, tools/call, /healthz)
├─ database_setup.py             # Creates and seeds SQLite DB (support.db)
├─ agents/
│  ├─ router_agent.py            # /card, /a2a/call (port 9201)
│  ├─ data_agent.py              # /card, /a2a/call (port 9102) - calls MCP tools
│  └─ support_agent.py           # /card, /a2a/call (port 9103)
├─ demos/
│  ├─ sequential_demo.py         # LangGraph sequential pattern demo
│  └─ router_demo.py             # LangGraph router pattern demo
├─ tests/
│  └─ run_tests.py               # Runs 5 assignment scenarios and prints logs/results
├─ result/
├─ requirements.txt
└─ README.md
```

---

## Requirements

- **Python 3.10+**
- macOS / Linux / Windows (WSL recommended on Windows)
- (Optional) **MCP Inspector** (Node.js required): `npx @modelcontextprotocol/inspector`

---

## Quick start

### 1) Create & activate a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 2) Initialize the database

```bash
python database_setup.py
# This creates/overwrites support.db with seed customers + tickets
```

### 3) Start all services (recommended)

```bash
bash run_all.sh
```

It launches:

- MCP server on http://127.0.0.1:9010
- Data agent on http://127.0.0.1:9102
- Support agent on http://127.0.0.1:9103
- Router agent on http://127.0.0.1:9201

Prefer separate terminals? Start each with:

```bash
uvicorn mcp_server:app --host 0.0.0.0 --port 9010
uvicorn agents.data_agent:app --host 0.0.0.0 --port 9102
uvicorn agents.support_agent:app --host 0.0.0.0 --port 9103
uvicorn agents.router_agent:app --host 0.0.0.0 --port 9201
```

---

## Sanity checks

### MCP health

```bash
curl -s http://127.0.0.1:9010/healthz
# {"ok": true}
```

### MCP tools/list (JSON-RPC)

```bash
curl -s -X POST http://127.0.0.1:9010/mcp \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":"x","method":"tools/list"}' | jq .
```

You should see tool entries with `inputSchema` for:
`get_customer`, `list_customers`, `update_customer`, `get_customer_history`, `create_ticket`.

### MCP tools/call example

```bash
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
```

### A2A agent checks

Each agent exposes:

- `GET /card` → agent card (id, name, capabilities)
- `POST /a2a/call` → JSON-RPC-like call

Example payload:

```json
{ "tool": "<name>", "arguments": { ... } }
```

#### Data Agent

```bash
curl -s http://127.0.0.1:9102/card | jq .
curl -s -X POST http://127.0.0.1:9102/a2a/call \
  -H 'Content-Type: application/json' \
  -d '{"tool":"get_customer","arguments":{"customer_id":5}}' | jq .
```

#### Support Agent

```bash
curl -s http://127.0.0.1:9103/card | jq .
curl -s -X POST http://127.0.0.1:9103/a2a/call \
  -H 'Content-Type: application/json' \
  -d '{"tool":"create_ticket","arguments":{"customer_id":1,"issue":"cannot login","priority":"high"}}' | jq .
```

#### Router Agent

```bash
curl -s http://127.0.0.1:9201/card | jq .
curl -s -X POST http://127.0.0.1:9201/a2a/call \
  -H 'Content-Type: application/json' \
  -d '{"task":"route","text":"create ticket for customer 1: cannot pay",
       "args":{"customer_id":1,"issue":"cannot pay","priority":"high"}}' | jq .
```

---

## MCP Inspector (independent client)

Keep the MCP server running on `:9010`, then in a new terminal:

```bash
npx @modelcontextprotocol/inspector
```

In the Inspector UI:

- Transport: **Streamable HTTP**
- URL: `http://127.0.0.1:9010/mcp`

Click **Connect → Initialize**, then **Tools** to view the list. Try `tools/call` with:

```json
{
  "tool": "get_customer",
  "arguments": { "customer_id": 5 }
}
```

Save screenshots into `docs/`:

- `docs/inspector-tools-list.png`
- `docs/inspector-tools-call.png`

---

## Run end-to-end tests (5 scenarios)

```bash
python tests/run_tests.py
```

Expected: five blocks (Simple, Coordinated, Complex, Escalation, Multi-Intent) with Route, Logs, and a Final answer.

---

## LangGraph demos (optional)

Sequential pattern:

```bash
python demos/sequential_demo.py
```

Router pattern:

```bash
python demos/router_demo.py
```

Both demos require `OPENAI_API_KEY` if they call an LLM. You can run them with mock tool logic if you prefer not to invoke an external model.

---

## Troubleshooting

**Port already in use**

```bash
lsof -i :9010
kill -9 <PID>
```

**MCP Inspector “422 Unprocessable Entity”**

- Ensure JSON-RPC includes `"jsonrpc":"2.0"`, a string `id`, and the correct `method`.
- `tools/list` must return `inputSchema` for every tool.

**Read timeout / connection refused**

- Start MCP first, then Data, Support, then Router.
- Confirm `/healthz` returns `{"ok":true}`.

**DB got messy while testing**

```bash
rm -f support.db
python database_setup.py
```

---

## Environment & versions

See `requirements.txt`. If you change versions, ensure the project still passes:

- `tools/list` shows `inputSchema`
- `tools/call` works for all tools
- `/card` and `/a2a/call` work on all agents
- `tests/run_tests.py` prints five passing scenarios

---

## Suggested resume/portfolio title

**Multi-Agent Customer Service Platform (MCP + A2A + LangGraph)**
