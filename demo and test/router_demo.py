# =====================================================
# Router-Based Multi-Agent System (No API keys required)
# Router -> BillingAgent / ShippingAgent / ProductAgent
# =====================================================

from typing import TypedDict, Optional, List
from langgraph.graph import StateGraph, START, END


# ---------- Shared state ----------
class SupportState(TypedDict, total=False):
    input: str
    route: Optional[str]
    response: Optional[str]
    logs: List[str]


# ---------- Tiny "tools" for specialists ----------
def refund_tool(issue: str) -> str:
    return f"[Billing] Refund initiated for: '{issue}'. ETA 3–5 business days."

def verify_payment_tool(issue: str) -> str:
    return f"[Billing] Payment verified for: '{issue}'. No anomalies found."

def shipping_inquiry_tool(issue: str) -> str:
    return f"[Shipping] Tracking investigation opened for: '{issue}'."

def address_update_tool(issue: str) -> str:
    return f"[Shipping] Address update submitted for: '{issue}'."

def product_replacement_tool(issue: str) -> str:
    return f"[Product] Replacement order created for: '{issue}'."

def warranty_claim_tool(issue: str) -> str:
    return f"[Product] Warranty claim filed for: '{issue}'."


# ---------- Agents ----------
def router_agent(state: SupportState) -> SupportState:
    text = state["input"].lower()
    if ("charge" in text) or ("refund" in text) or ("billing" in text) or ("invoice" in text):
        route = "billing"
    elif ("delay" in text) or ("delivery" in text) or ("shipping" in text) or ("package" in text):
        route = "shipping"
    elif ("broken" in text) or ("defect" in text) or ("not working" in text) or ("damaged" in text):
        route = "product"
    else:
        route = "product"  # default

    logs = state.get("logs", [])
    logs.append(f"Router → route='{route}'")
    return {"route": route, "logs": logs}

def billing_agent(state: SupportState) -> SupportState:
    issue = state["input"]
    # Simple heuristic: if both 'charge' and 'refund' present, do refund; otherwise verify
    lower = issue.lower()
    if ("refund" in lower) or ("charged twice" in lower) or ("double charge" in lower):
        result = refund_tool(issue)
        tool = "refund_tool"
    else:
        result = verify_payment_tool(issue)
        tool = "verify_payment_tool"

    logs = state.get("logs", [])
    logs.append(f"BillingAgent → {tool}")
    return {"response": result, "logs": logs}

def shipping_agent(state: SupportState) -> SupportState:
    issue = state["input"]
    lower = issue.lower()
    if ("address" in lower) or ("wrong address" in lower):
        result = address_update_tool(issue)
        tool = "address_update_tool"
    else:
        result = shipping_inquiry_tool(issue)
        tool = "shipping_inquiry_tool"

    logs = state.get("logs", [])
    logs.append(f"ShippingAgent → {tool}")
    return {"response": result, "logs": logs}

def product_agent(state: SupportState) -> SupportState:
    issue = state["input"]
    lower = issue.lower()
    if ("warranty" in lower) or ("guarantee" in lower):
        result = warranty_claim_tool(issue)
        tool = "warranty_claim_tool"
    else:
        result = product_replacement_tool(issue)
        tool = "product_replacement_tool"

    logs = state.get("logs", [])
    logs.append(f"ProductAgent → {tool}")
    return {"response": result, "logs": logs}


# ---------- Build graph ----------
graph = StateGraph(SupportState)
graph.add_node("Router", router_agent)
graph.add_node("BillingAgent", billing_agent)
graph.add_node("ShippingAgent", shipping_agent)
graph.add_node("ProductAgent", product_agent)

graph.add_edge(START, "Router")

def route_decision(state: SupportState) -> str:
    r = (state.get("route") or "").lower()
    if r == "billing":
        return "BillingAgent"
    if r == "shipping":
        return "ShippingAgent"
    return "ProductAgent"

graph.add_conditional_edges(
    "Router",
    route_decision,
    {
        "BillingAgent": "BillingAgent",
        "ShippingAgent": "ShippingAgent",
        "ProductAgent": "ProductAgent",
    },
)

graph.add_edge("BillingAgent", END)
graph.add_edge("ShippingAgent", END)
graph.add_edge("ProductAgent", END)

router_system = graph.compile()


# ---------- Demo run ----------
if __name__ == "__main__":
    tests = [
        "I was charged twice for my order and need a refund.",
        "My package still hasn’t arrived and delivery shows delayed.",
        "The item arrived broken and not working."
    ]

    print("=== Router-Based Multi-Agent Demo ===")
    for q in tests:
        out = router_system.invoke({"input": q, "logs": []})
        print("\n---")
        print(f"Input: {q}")
        print("Logs:")
        for line in out["logs"]:
            print(f"  - {line}")
        print(f"Final Response:\n{out['response']}")
