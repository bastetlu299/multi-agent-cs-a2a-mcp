# =====================================================
# Sequential Multi-Agent Workflow (No API keys required)
# IntentAnalyzer -> KnowledgeRetriever -> ResponseGenerator
# =====================================================

from typing import TypedDict, Optional, List
from langgraph.graph import StateGraph, START, END


# ---------- Shared state ----------
class SupportState(TypedDict, total=False):
    input: str
    intent: Optional[str]
    knowledge: Optional[str]
    response: Optional[str]
    logs: List[str]


# ---------- Tiny "tools" (deterministic) ----------
def detect_intent(message: str) -> str:
    m = message.lower()
    if ("charge" in m) or ("refund" in m) or ("billing" in m):
        return "billing"
    if ("delay" in m) or ("delivery" in m) or ("shipping" in m):
        return "shipping"
    if ("broken" in m) or ("defect" in m) or ("not working" in m):
        return "product"
    return "other"

def lookup_kb(intent: str) -> str:
    kb = {
        "billing":  "Policy: duplicate charges are refunded in 5 business days.",
        "shipping": "Policy: delivery delays can be tracked via courier site.",
        "product":  "Policy: defective items replaced within 30 days.",
        "other":    "Policy: general inquiries are handled by care team."
    }
    return kb.get(intent, "Policy: no specific policy found.")

def generate_response(user_input: str, knowledge: str) -> str:
    return (
        "Customer Support:\n"
        f"- Your message: {user_input}\n"
        f"- Guidance: {knowledge}\n"
        "If you need anything else, let us know."
    )


# ---------- Agents ----------
def intent_analyzer(state: SupportState) -> SupportState:
    intent = detect_intent(state["input"])
    logs = state.get("logs", [])
    logs.append(f"IntentAnalyzer → intent='{intent}'")
    return {"intent": intent, "logs": logs}

def knowledge_retriever(state: SupportState) -> SupportState:
    intent = state["intent"]
    knowledge = lookup_kb(intent or "other")
    logs = state.get("logs", [])
    logs.append("KnowledgeRetriever → KB fetched")
    return {"knowledge": knowledge, "logs": logs}

def response_generator(state: SupportState) -> SupportState:
    reply = generate_response(state["input"], state["knowledge"] or "")
    logs = state.get("logs", [])
    logs.append("ResponseGenerator → response composed")
    return {"response": reply, "logs": logs}


# ---------- Build graph ----------
graph = StateGraph(SupportState)
graph.add_node("IntentAnalyzer", intent_analyzer)
graph.add_node("KnowledgeRetriever", knowledge_retriever)
graph.add_node("ResponseGenerator", response_generator)

graph.add_edge(START, "IntentAnalyzer")
graph.add_edge("IntentAnalyzer", "KnowledgeRetriever")
graph.add_edge("KnowledgeRetriever", "ResponseGenerator")
graph.add_edge("ResponseGenerator", END)

sequential_pipeline = graph.compile()


# ---------- Demo run ----------
if __name__ == "__main__":
    user_msg = "My order was charged twice but I only received one item."
    result = sequential_pipeline.invoke({"input": user_msg, "logs": []})

    print("=== Sequential Multi-Agent Demo ===")
    print(f"Input: {user_msg}\n")
    print("Logs:")
    for line in result["logs"]:
        print(f"  - {line}")
    print("\nFinal Response:\n")
    print(result["response"])
