from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from src.agents.nodes import (
    AgentRuntime,
    audience_agent,
    compliance_agent,
    competitor_agent,
    creative_agent,
    critic_agent,
    finalize,
    load_context,
    memory_commit,
    orchestrator_assign_tasks,
    orchestrator_review,
    planner_agent,
    reflection_agent,
    schedule_assets,
    trend_agent,
)
from src.workflow.state import WorkflowState


def _route_after_review(state: WorkflowState) -> str:
    return state.get("route_decision", "blocked")


def _route_after_finalize(state: WorkflowState) -> str:
    return "reflect" if state.get("run_reflection", False) else "done"


def build_workflow(runtime: AgentRuntime):
    graph = StateGraph(WorkflowState)

    graph.add_node("load_context", lambda state: load_context(runtime, state))
    graph.add_node("orchestrator_assign_tasks", lambda state: orchestrator_assign_tasks(runtime, state))
    graph.add_node("trend_research", lambda state: trend_agent(runtime, state))
    graph.add_node("audience_research", lambda state: audience_agent(runtime, state))
    graph.add_node("competitor_research", lambda state: competitor_agent(runtime, state))
    graph.add_node("planner", lambda state: planner_agent(runtime, state))
    graph.add_node("creative", lambda state: creative_agent(runtime, state))
    graph.add_node("compliance", lambda state: compliance_agent(runtime, state))
    graph.add_node("critic", lambda state: critic_agent(runtime, state))
    graph.add_node("orchestrator_review", lambda state: orchestrator_review(runtime, state))
    graph.add_node("schedule", lambda state: schedule_assets(runtime, state))
    graph.add_node("finalize", lambda state: finalize(runtime, state))
    graph.add_node("reflection", lambda state: reflection_agent(runtime, state))
    graph.add_node("memory_commit", lambda state: memory_commit(runtime, state))

    graph.add_edge(START, "load_context")
    graph.add_edge("load_context", "orchestrator_assign_tasks")

    graph.add_edge("orchestrator_assign_tasks", "trend_research")
    graph.add_edge("orchestrator_assign_tasks", "audience_research")
    graph.add_edge("orchestrator_assign_tasks", "competitor_research")

    graph.add_edge("trend_research", "planner")
    graph.add_edge("audience_research", "planner")
    graph.add_edge("competitor_research", "planner")

    graph.add_edge("planner", "creative")

    graph.add_edge("creative", "compliance")
    graph.add_edge("creative", "critic")

    graph.add_edge("compliance", "orchestrator_review")
    graph.add_edge("critic", "orchestrator_review")

    graph.add_conditional_edges(
        "orchestrator_review",
        _route_after_review,
        {
            "revise": "creative",
            "approved": "schedule",
            "blocked": "finalize",
        },
    )

    graph.add_edge("schedule", "finalize")
    graph.add_conditional_edges(
        "finalize",
        _route_after_finalize,
        {"reflect": "reflection", "done": END},
    )
    graph.add_edge("reflection", "memory_commit")
    graph.add_edge("memory_commit", END)

    return graph.compile()
