import asyncio
from typing import List, Dict, Any, Optional, Callable, Awaitable
from datetime import datetime, timezone
import json
import os
from langchain_openai import ChatOpenAI
from .core.state import AffiliateSystemState, AffiliateLead, LeadStatus

class MasterOrchestrator:
    """
    Orchestrates the workflow between different agents in the affiliate system.
    Determines which agent should run next based on current state and business rules.
    """
    def __init__(self,
                 llm_client: Any,
                 composio_client: Any,
                 agent_config: Dict[str, Dict[str, Any]],
                 workflow_config: Dict[str, Any],
                 agent_instances: Optional[Dict[str, Any]] = None):
        """
        Initializes the MasterOrchestrator.

        Args:
            llm_client: Client for interacting with the Language Model.
            composio_client: Client for Composio tool integration.
            agent_config: Configuration for each agent in the system.
            workflow_config: Configuration for workflow orchestration.
            agent_instances: Optional pre-initialized agent instances.
        """
        self.llm_client = llm_client
        self.composio_client = composio_client
        self.agent_config = agent_config
        self.workflow_config = workflow_config

        # Initialize agent instances if not provided
        self.agent_instances = agent_instances if agent_instances else {}

    async def initialize_agents(self):
        """
        Initializes all required agent instances if not already provided.
        """
        from .agents.social_scout_agent import SocialScoutAgent
        from .agents.outreach_agent import OutreachAgent
        from .agents.crm_agent import CRMAgent
        from .agents.commission_agent import CommissionAgent
        from .agents.performance_agent import PerformanceAgent
        from .agents.payment_agent import PaymentAgent

        # Only initialize agents that don't already exist
        if "social_scout" not in self.agent_instances:
            self.agent_instances["social_scout"] = SocialScoutAgent(
                llm_client=self.llm_client,
                composio_client=self.composio_client,
                scouting_config=self.agent_config.get("social_scout", {})
            )

        if "outreach" not in self.agent_instances:
            self.agent_instances["outreach"] = OutreachAgent(
                llm_client=self.llm_client,
                composio_client=self.composio_client,
                outreach_config=self.agent_config.get("outreach", {})
            )

        if "crm" not in self.agent_instances:
            self.agent_instances["crm"] = CRMAgent(
                composio_client=self.composio_client,
                crm_config=self.agent_config.get("crm", {})
            )

        if "commission" not in self.agent_instances:
            self.agent_instances["commission"] = CommissionAgent(
                composio_client=self.composio_client,
                commission_config=self.agent_config.get("commission", {})
            )

        if "performance" not in self.agent_instances:
            self.agent_instances["performance"] = PerformanceAgent(
                llm_client=self.llm_client,
                composio_client=self.composio_client,
                performance_config=self.agent_config.get("performance", {})
            )

        if "payment" not in self.agent_instances:
            self.agent_instances["payment"] = PaymentAgent(
                composio_client=self.composio_client,
                payment_config=self.agent_config.get("payment", {})
            )

    async def _select_outreach_targets(self, state: AffiliateSystemState) -> AffiliateSystemState:
        """
        Selects prospects from the pool to target for outreach.
        Uses an LLM to prioritize and select the best targets.
        """
        print("Orchestrator: Selecting outreach targets...")

        # Get all prospects that are NEW (not contacted yet)
        prospects = state.prospects # Use Pydantic attribute access
        eligible_prospects = [p for p in prospects if p.status == LeadStatus.NEW and p.contact_info.get("email")]

        if not eligible_prospects:
            print("Orchestrator: No eligible prospects found for outreach.")
            state.outreach_targets = [] # Use Pydantic attribute access
            return state

        # If there are only a few eligible prospects, select them all
        max_outreach = self.workflow_config.get("max_outreach_per_cycle", 10)
        if len(eligible_prospects) <= max_outreach:
            state.outreach_targets = eligible_prospects # Use Pydantic attribute access
            print(f"Orchestrator: Selected all {len(eligible_prospects)} eligible prospects for outreach.")
            return state

        # For larger numbers, we'll use scoring to prioritize
        # Sort by combined score (content quality + relevance)
        eligible_prospects.sort(key=lambda p: p.content_quality_score + p.relevance_score, reverse=True)

        # Select top prospects up to max_outreach
        selected_prospects = eligible_prospects[:max_outreach]
        state.outreach_targets = selected_prospects # Use Pydantic attribute access

        print(f"Orchestrator: Selected {len(selected_prospects)} top prospects for outreach out of {len(eligible_prospects)} eligible.")
        return state

    async def _select_commissions_for_payment(self, state: AffiliateSystemState) -> AffiliateSystemState:
        """
        Selects commissions that are ready for payment processing.
        """
        from .core.state import CommissionStatus

        print("Orchestrator: Selecting commissions for payment...")

        # Get all commissions in PENDING status and mark them as APPROVED for payment
        commissions = state.commissions_log # Use Pydantic attribute access
        pending_commissions = [c for c in commissions if c.status == CommissionStatus.PENDING]

        # In a real system, you might have an approval workflow here
        # For this example, we'll automatically approve all pending commissions
        for commission in pending_commissions:
            commission.status = CommissionStatus.APPROVED

        print(f"Orchestrator: Approved {len(pending_commissions)} commissions for payment.")
        return state

    async def _determine_next_agent(self, state: AffiliateSystemState) -> str:
        """
        Determines which agent should run next based on the current state.
        """
        # Get current task from state
        current_task = state.current_task if state.current_task is not None else "initial"

        # Simple state machine to determine next agent
        if current_task == "initial" or current_task == "cycle_complete":
            # Start a new cycle with prospect scouting
            return "social_scout"

        elif current_task == "prospects_found":
            # After finding prospects, select targets and run outreach
            return "select_outreach_targets"

        elif current_task == "outreach_targets_selected":
            # After selecting targets, execute outreach
            return "outreach"

        elif current_task == "outreach_complete":
            # After outreach, update CRM
            return "crm"

        elif current_task == "crm_updated":
            # After CRM update, track commissions
            return "commission"

        elif current_task == "commissions_processed":
            # After tracking commissions, select which ones to pay
            return "select_commissions_for_payment"

        elif current_task == "commissions_approved":
            # After approving commissions, process payments
            return "payment"

        elif current_task == "payments_processed":
            # After processing payments, analyze performance
            return "performance"

        else:
            # Default to performance analysis if the state is unclear
            print(f"Orchestrator: Unrecognized current_task '{current_task}'. Defaulting to performance analysis.")
            return "performance"

    async def orchestrate(self, state: AffiliateSystemState) -> AffiliateSystemState:
        pass
        # Ensure all agents are initialized
        if not self.agent_instances:
            await self.initialize_agents()

        # Determine which agent should run next
        next_agent = await self._determine_next_agent(state)
        print(f"Orchestrator: Next agent to run: {next_agent}")

        # Run the appropriate agent or internal function
        try:
            if next_agent == "social_scout":
                state = await self.agent_instances["social_scout"].scout_prospects(state)
                state.current_task = "prospects_found" # Use Pydantic attribute access

            elif next_agent == "select_outreach_targets":
                state = await self._select_outreach_targets(state)
                state.current_task = "outreach_targets_selected" # Use Pydantic attribute access

            elif next_agent == "outreach":
                state = await self.agent_instances["outreach"].execute_outreach(state)
                state.current_task = "outreach_complete" # Use Pydantic attribute access

            elif next_agent == "crm":
                state = await self.agent_instances["crm"].manage_affiliate_data(state)
                state.current_task = "crm_updated" # Use Pydantic attribute access

            elif next_agent == "commission":
                state = await self.agent_instances["commission"].track_commissions(state)
                state.current_task = "commissions_processed" # Use Pydantic attribute access

            elif next_agent == "select_commissions_for_payment":
                state = await self._select_commissions_for_payment(state)
                state.current_task = "commissions_approved" # Use Pydantic attribute access

            elif next_agent == "payment":
                state = await self.agent_instances["payment"].process_payments(state)
                state.current_task = "payments_processed" # Use Pydantic attribute access

            elif next_agent == "performance":
                state = await self.agent_instances["performance"].analyze_performance(state)
                state.current_task = "cycle_complete" # Use Pydantic attribute access

            else:
                print(f"Orchestrator: Unknown agent '{next_agent}'. No action taken.")
                state.last_error = f"Unknown agent: {next_agent}" # Use Pydantic attribute access

        except Exception as e:
            error_message = f"Error running {next_agent}: {str(e)}"
            print(f"Orchestrator: {error_message}")
            state.last_error = error_message # Use Pydantic attribute access

        # Log the current state (simplified version)
        timestamp = datetime.now(timezone.utc).isoformat()
        print(f"Orchestrator: State at {timestamp}: current_task={state.current_task}, "
              f"prospects={len(state.prospects)}, "
              f"active_affiliates={len(state.active_affiliates)}, "
              f"commissions={len(state.commissions_log)}")

        return state
