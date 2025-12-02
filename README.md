# Multi-Agent Customer Service (A2A + MCP)

This project implements the assignment requirements:

- **MCP server** (JSON-RPC over Streamable HTTP) exposing `tools/list` and `tools/call`, testable via **MCP Inspector**.
- **Agents with A2A interfaces** (Router, Customer Data, Support) implemented with **LangGraph** (plus simple sequential and router demos).
- **SQLite** demo database with seed script.

> Protocols required by the assignment:
> - **MCP** for database tools (`get_customer`, `list_customers`, `update_customer`, `create_ticket`, `get_customer_history`)
> - **A2A** via LangGraph for multi-agent coordination (sequential and router patterns)

---

## Repository Structure

├─ mcp_server.py # FastAPI JSON-RPC MCP server (/mcp, /healthz)
├─ database_setup.py # Creates support.db and seeds demo data
├─ run_tests.py # Runs the 5 required test scenarios
├─ router_demo.py # (Optional) Router pattern demo with LangGraph
├─ sequential_demo.py # (Optional) Sequential pattern demo with LangGraph
├─ requirements.txt # Python dependencies
└─ README.md


---

## Prerequisites
- **Python** 3.10+ (3.11/3.12 recommended)
- **Node.js** 18+ (only for MCP Inspector)
- macOS / Linux / Windows (WSL) supported

---

## 1) Create & Activate Virtual Environment

### macOS / Linux
```bash
python3 -m venv .venv
source .venv/bin/activate
nstall Dependencies
pip install -U pip
pip install -r requirements.txt

3) Initialize the Demo Database
python database_setup.py


This creates support.db with sample customers and tickets. Re-run anytime to reset.

4) Run the MCP Server
python mcp_server.py


MCP JSON-RPC endpoint: http://127.0.0.1:9010/mcp

Health check: http://127.0.0.1:9010/healthz

Quick checks (new terminal, same venv):

curl -s http://127.0.0.1:9010/healthz
# → {"ok": true}

curl -s -X POST http://127.0.0.1:9010/mcp \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | jq


If the port is busy, stop the other process or change the port at the bottom of mcp_server.py.

5) (Optional) Use MCP Inspector

Start the proxy:

npx @modelcontextprotocol/inspector


Copy the Session token printed in the terminal.

Open the UI (usually auto-opens at http://localhost:6274). Then:

Transport Type: Streamable HTTP

URL: http://127.0.0.1:9010/mcp

Connection Type: Via Proxy

Authentication → Custom Headers
Add header:

Name: Authorization

Value: Bearer <paste-session-token-here>
Toggle the header ON.

Click Connect → Tools → List Tools → choose a tool → Run Tool.

This server returns inputSchema for every tool, so Inspector can render the forms.

6) Run the End-to-End Tests
python run_tests.py


You should see the five scenarios:

Simple Query (single MCP call)

Coordinated Query (router → data → support)

Complex Query (negotiation; data + support)

Escalation (router → support)

Multi-Intent (update + history)
