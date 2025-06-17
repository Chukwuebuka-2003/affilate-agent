import os
import asyncio
from typing import Dict, Any, Optional
import json
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from pydantic import SecretStr
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

# Import state definitions
from .core.state import AffiliateSystemState, AffiliateLead, LeadStatus

# Import agents
from .agents.social_scout_agent import SocialScoutAgent
from .agents.outreach_agent import OutreachAgent
from .agents.crm_agent import CRMAgent
from .agents.commission_agent import CommissionAgent
from .agents.performance_agent import PerformanceAgent
from .agents.payment_agent import PaymentAgent
from .orchestrator import MasterOrchestrator

# Load environment variables
load_dotenv()

def get_default_config() -> Dict[str, Any]:
    """
    Returns the default configuration for the affiliate system.
    These values can be overridden by user-supplied config.
    """
    return {
        "agent_config": {
            "social_scout": {
                "platforms": ["youtube", "twitter", "linkedin", "instagram"],
                "keywords": ["AI tools", "SaaS review", "machine learning", "productivity tools"],
                "min_audience_size": 1000,
                "scoring_criteria": "Evaluate the prospect based on content quality related to our niche (e.g., AI, SaaS, productivity) and relevance of their audience to our target customers."
            },
            "outreach": {
                "outreach_method": "email",
                "email_subject_template": "Collaboration Opportunity: {LEAD_NAME} x Our Brand",
                "message_templates": {
                    "default": "Hi {LEAD_NAME}, I noticed your impressive content on {LEAD_PLATFORM} and believe our audience would love your perspective. We're offering a 70% commission on our affiliate program. Would you be interested in learning more?"
                },
                "max_outreach_per_run": 10
            },
            "crm": {
                "tool_id": "hubspot",
                "affiliate_status_field": "affiliate_status",
                "default_owner_id": "default_owner"
            },
            "commission": {
                "default_commission_rate": 0.7,
                "recurring_commission_rate": 0.05,
                "performance_tiers": {
                    "tier1": {"threshold": 10, "bonus": 0.05},
                    "tier2": {"threshold": 25, "bonus": 0.10},
                    "tier3": {"threshold": 50, "bonus": 0.15}
                },
                "payment_threshold": 50.0,
                "attribution_model": {
                    "firstClick": 0.3,
                    "lastClick": 0.4,
                    "linear": 0.3
                }
            },
            "performance": {
                "analysis_period_days": 30,
                "report_metrics": ["conversion_rate", "epc", "roi"],
                "alert_thresholds": {
                    "low_conversion_rate": 0.05,
                    "low_epc": 0.5,
                    "negative_roi": 0.0
                }
            },
            "payment": {
                "payment_methods": ["stripe_connect", "paypal", "crypto"],
                "batch_payments": True,
                "minimum_payment": 50.0,
                "payment_schedule": "weekly",
                "default_currency": "USD"
            }
        },
        "workflow_config": {
            "max_outreach_per_cycle": 10,
            "auto_approve_commissions": True,
            "auto_run_schedule": "daily"
        }
    }

def create_affiliate_system(config: Optional[Dict[str, Any]] = None) -> Any:
    """
    Creates and configures the affiliate marketing system LangGraph.

    Args:
        config: Optional configuration to override defaults.

    Returns:
        The compiled LangGraph workflow.
    """
    # Merge with default config
    default_config = get_default_config()
    if config:
        # Recursively merge configs
        for key, value in config.items():
            if key in default_config and isinstance(value, dict) and isinstance(default_config[key], dict):
                default_config[key].update(value)
            else:
                default_config[key] = value

    config = default_config

    # Extract configs
    agent_config = config.get("agent_config", {})
    workflow_config = config.get("workflow_config", {})

    # Initialize LLM client
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        raise ValueError("OpenAI API key is required. Set OPENAI_API_KEY in your environment (e.g., .env file).")

    llm_client = ChatOpenAI(
        api_key=SecretStr(openai_api_key),
        model="gpt-4o-mini",  # Adjust based on your needs
        temperature=0.2
    )

    # Initialize Composio client
    composio_api_key = os.getenv("COMPOSIO_API_KEY")
    if not composio_api_key:
        raise ValueError("Composio API key is required. Set COMPOSIO_API_KEY in your environment (e.g., .env file).")

    # Import the appropriate Composio client based on what's available
    try:
        from composio_langgraph import ComposioToolSet
        composio_client = ComposioToolSet(api_key=SecretStr(composio_api_key))
    except ImportError:
        try:
            from composio_openai import ComposioToolSet
            composio_client = ComposioToolSet(api_key=SecretStr(composio_api_key))
        except ImportError:
            # Mock Composio client for testing
            from .agents import Composio
            composio_client = Composio(api_key=composio_api_key)
            print("Warning: Using mock Composio client. Install composio_langgraph or composio_openai for production use.")

    # Initialize the orchestrator
    orchestrator = MasterOrchestrator(
        llm_client=llm_client,
        composio_client=composio_client,
        agent_config=agent_config,
        workflow_config=workflow_config
    )

    # Create the LangGraph
    workflow = StateGraph(AffiliateSystemState)

    # Add the orchestrator node - single node that manages all agent calls
    workflow.add_node("orchestrator", orchestrator.orchestrate)

    # Add edges
    workflow.add_edge(START, "orchestrator")

    # Add conditional edge to either continue the cycle or end
    def should_continue(state: AffiliateSystemState) -> str:
        """Determines if the workflow should continue or end based on state."""
        current_task = state.get("current_task")
        if current_task == "cycle_complete":
            # In a continuous system, you might always return to orchestrator
            # But for API-driven usage, we'll end here and let API endpoints trigger new cycles
            return END
        else:
            # Continue the cycle
            return "orchestrator"

    workflow.add_conditional_edges(
        "orchestrator",
        should_continue,
        {
            END: END,
            "orchestrator": "orchestrator"
        }
    )

    # Add memory for state persistence
    memory = MemorySaver()

    # Compile the graph
    system = workflow.compile(checkpointer=memory)

    return system

async def run_example():
    """
    Example usage of the affiliate system.
    """
    # Create the system
    system = create_affiliate_system()

    # Initial state
    initial_state = {
        "prospects": [],
        "outreach_targets": [],
        "active_affiliates": [],
        "commissions_log": [],
        "crm_update_status": None,
        "last_error": None,
        "current_task_description": "Starting initial scout.",
        "campaign_performance_report": None,
        "current_task": "initial"
    }

    # Run the system for a few cycles
    state = initial_state
    for i in range(3):
        print(f"\n--- Running Cycle {i+1} ---")
        state = await system.invoke(state)

        # Print some stats
        print(f"\nCycle {i+1} Complete:")
        print(f"Current Task: {state.get('current_task')}")
        print(f"Description: {state.get('current_task_description')}")
        print(f"Prospects: {len(state.get('prospects', []))}")
        print(f"Active Affiliates: {len(state.get('active_affiliates', []))}")
        print(f"Commissions: {len(state.get('commissions_log', []))}")

        if state.get("last_error"):
            print(f"Error: {state.get('last_error')}")

        # Sleep between cycles
        await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(run_example())
