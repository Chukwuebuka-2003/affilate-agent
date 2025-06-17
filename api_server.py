from fastapi import FastAPI, BackgroundTasks, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn
import asyncio
import json
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import os

# Import the LangGraph system
from .main import create_affiliate_system, get_default_config

# Import state definitions
from .core.state import AffiliateSystemState, AffiliateLead, LeadStatus, CommissionStatus

# Create FastAPI app
app = FastAPI(title="AI Affiliate Marketing System")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For development - restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global campaign registry
campaign_registry = {}

# Pydantic models for API requests
class CampaignConfig(BaseModel):
    name: str = Field(..., description="Name of the campaign")
    description: Optional[str] = Field(None, description="Campaign description")
    config: Dict[str, Any] = Field(..., description="Campaign configuration object")

class OutreachTargetRequest(BaseModel):
    campaign_id: str = Field(..., description="ID of the campaign")
    lead_ids: List[str] = Field(..., description="List of lead IDs to target for outreach")

class LeadQuery(BaseModel):
    campaign_id: str = Field(..., description="ID of the campaign")
    status: Optional[str] = Field(None, description="Filter by lead status")
    platform: Optional[str] = Field(None, description="Filter by platform")
    min_audience_size: Optional[int] = Field(None, description="Minimum audience size")
    search_term: Optional[str] = Field(None, description="Search term for lead name or notes")

# Helper function to clean state for JSON serialization
def clean_state_for_json(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Converts state objects to serializable format
    """
    # Deep copy to avoid modifying original
    clean_state = {}

    # Handle prospects
    if "prospects" in state:
        clean_state["prospects"] = []
        for prospect in state["prospects"]:
            if isinstance(prospect, AffiliateLead):
                clean_state["prospects"].append({
                    "lead_id": prospect.lead_id,
                    "name": prospect.name,
                    "platform": prospect.platform,
                    "audience_size": prospect.audience_size,
                    "engagement_rate": prospect.engagement_rate,
                    "content_quality_score": prospect.content_quality_score,
                    "relevance_score": prospect.relevance_score,
                    "status": prospect.status.value if hasattr(prospect.status, "value") else str(prospect.status),
                    "contact_info": prospect.contact_info,
                    "outreach_history": prospect.outreach_history,
                    "notes": prospect.notes
                })
            else:
                # Already a dict
                clean_state["prospects"].append(prospect)

    # Handle active_affiliates
    if "active_affiliates" in state:
        clean_state["active_affiliates"] = []
        for affiliate in state["active_affiliates"]:
            if isinstance(affiliate, AffiliateLead):
                clean_state["active_affiliates"].append({
                    "lead_id": affiliate.lead_id,
                    "name": affiliate.name,
                    "platform": affiliate.platform,
                    "status": affiliate.status.value if hasattr(affiliate.status, "value") else str(affiliate.status),
                    "contact_info": affiliate.contact_info
                })
            else:
                # Already a dict
                clean_state["active_affiliates"].append(affiliate)

    # Handle commissions
    if "commissions_log" in state:
        clean_state["commissions_log"] = []
        for commission in state["commissions_log"]:
            if hasattr(commission, "commission_id"):
                clean_state["commissions_log"].append({
                    "commission_id": commission.commission_id,
                    "affiliate_id": commission.affiliate_id,
                    "sale_amount": commission.sale_amount,
                    "commission_rate": commission.commission_rate,
                    "commission_amount": commission.commission_amount,
                    "sale_date": commission.sale_date,
                    "status": commission.status.value if hasattr(commission.status, "value") else str(commission.status)
                })
            else:
                # Already a dict
                clean_state["commissions_log"].append(commission)

    # Copy remaining fields that don't need special handling
    for key, value in state.items():
        if key not in clean_state and key not in ["prospects", "active_affiliates", "commissions_log"]:
            clean_state[key] = value

    return clean_state

@app.get("/")
async def root():
    """API root with basic info"""
    return {
        "name": "AI Affiliate Marketing System",
        "version": "1.0.0",
        "docs_url": "/docs",
        "description": "LangGraph + Composio powered affiliate recruitment and management system"
    }

@app.post("/campaigns")
async def create_campaign(campaign_config: CampaignConfig, background_tasks: BackgroundTasks):
    """Create a new affiliate marketing campaign"""

    # Generate a unique ID for the campaign
    campaign_id = f"campaign_{datetime.now(timezone.utc).timestamp()}"

    # Merge user config with default config
    default_config = get_default_config()
    merged_config = {**default_config, **campaign_config.config}

    # Create a new LangGraph instance for this campaign
    system = create_affiliate_system(config=merged_config)

    # Initialize empty state
    initial_state = {
        "prospects": [],
        "outreach_targets": [],
        "active_affiliates": [],
        "commissions_log": [],
        "crm_update_status": None,
        "last_error": None,
        "current_task_description": "Campaign initialized.",
        "campaign_performance_report": None,
        "current_task": "initial",
        "name": campaign_config.name,
        "description": campaign_config.description,
        "created_at": datetime.now(timezone.utc).isoformat()
    }

    # Register the campaign
    campaign_registry[campaign_id] = {
        "id": campaign_id,
        "name": campaign_config.name,
        "description": campaign_config.description,
        "system": system,
        "config": merged_config,
        "state": initial_state,
        "status": "initialized",
        "last_run": None
    }

    # Start the campaign in the background
    background_tasks.add_task(run_campaign_cycle, campaign_id)

    return {
        "id": campaign_id,
        "name": campaign_config.name,
        "description": campaign_config.description,
        "status": "started",
        "message": "Campaign created and initial cycle started."
    }

@app.get("/campaigns")
async def list_campaigns():
    """List all registered campaigns"""
    campaigns = []

    for campaign_id, campaign in campaign_registry.items():
        # Calculate summary statistics
        state = campaign.get("state", {})
        prospect_count = len(state.get("prospects", []))
        affiliate_count = len(state.get("active_affiliates", []))

        # Calculate total commission
        total_commission = 0.0
        for commission in state.get("commissions_log", []):
            if hasattr(commission, "commission_amount"):
                total_commission += commission.commission_amount
            elif isinstance(commission, dict) and "commission_amount" in commission:
                total_commission += commission["commission_amount"]

        campaigns.append({
            "id": campaign_id,
            "name": campaign.get("name", "Unnamed Campaign"),
            "description": campaign.get("description"),
            "status": campaign.get("status", "unknown"),
            "last_run": campaign.get("last_run"),
            "stats": {
                "prospects": prospect_count,
                "affiliates": affiliate_count,
                "commission": total_commission
            }
        })

    return campaigns

@app.get("/campaigns/{campaign_id}")
async def get_campaign(campaign_id: str):
    """Get details about a specific campaign"""
    if campaign_id not in campaign_registry:
        raise HTTPException(status_code=404, detail="Campaign not found")

    campaign = campaign_registry[campaign_id]

    # Clean state for JSON serialization
    clean_state = clean_state_for_json(campaign["state"])

    return {
        "id": campaign_id,
        "name": campaign.get("name", "Unnamed Campaign"),
        "description": campaign.get("description"),
        "status": campaign.get("status", "unknown"),
        "last_run": campaign.get("last_run"),
        "config": campaign.get("config"),
        "state": clean_state
    }

@app.post("/campaigns/{campaign_id}/run")
async def run_campaign(campaign_id: str, background_tasks: BackgroundTasks):
    """Manually trigger a campaign cycle"""
    if campaign_id not in campaign_registry:
        raise HTTPException(status_code=404, detail="Campaign not found")

    # Get current status
    current_status = campaign_registry[campaign_id].get("status")

    if current_status == "running":
        return {"status": "already_running", "message": "Campaign is already running"}

    # Start the campaign in the background
    background_tasks.add_task(run_campaign_cycle, campaign_id)

    return {"status": "started", "message": "Campaign cycle started"}

@app.get("/campaigns/{campaign_id}/status")
async def get_campaign_status(campaign_id: str):
    """Get the current status of a campaign"""
    if campaign_id not in campaign_registry:
        raise HTTPException(status_code=404, detail="Campaign not found")

    campaign = campaign_registry[campaign_id]
    state = campaign.get("state", {})

    # Extract key metrics for the response
    prospect_count = len(state.get("prospects", []))
    affiliate_count = len(state.get("active_affiliates", []))

    # Calculate different status counts
    status_counts = {}
    for prospect in state.get("prospects", []):
        status_value = prospect.status.value if hasattr(prospect, "status") and hasattr(prospect.status, "value") else "unknown"
        if status_value not in status_counts:
            status_counts[status_value] = 0
        status_counts[status_value] += 1

    # Calculate total commission
    total_commission = 0.0
    for commission in state.get("commissions_log", []):
        if hasattr(commission, "commission_amount"):
            total_commission += commission.commission_amount
        elif isinstance(commission, dict) and "commission_amount" in commission:
            total_commission += commission["commission_amount"]

    return {
        "id": campaign_id,
        "name": campaign.get("name", "Unnamed Campaign"),
        "status": campaign.get("status", "unknown"),
        "last_run": campaign.get("last_run"),
        "current_task": state.get("current_task"),
        "current_task_description": state.get("current_task_description"),
        "last_error": state.get("last_error"),
        "metrics": {
            "prospects": prospect_count,
            "prospects_by_status": status_counts,
            "active_affiliates": affiliate_count,
            "total_commission": total_commission
        },
        "performance_report": state.get("campaign_performance_report")
    }

@app.post("/campaigns/{campaign_id}/outreach")
async def set_outreach_targets(campaign_id: str, request: OutreachTargetRequest):
    """Manually set specific leads as outreach targets"""
    if campaign_id not in campaign_registry:
        raise HTTPException(status_code=404, detail="Campaign not found")

    campaign = campaign_registry[campaign_id]
    state = campaign.get("state", {})

    # Find the prospects with the given IDs
    prospects = state.get("prospects", [])
    outreach_targets = []

    for lead_id in request.lead_ids:
        target = next((p for p in prospects if p.lead_id == lead_id), None)
        if target:
            outreach_targets.append(target)

    if not outreach_targets:
        raise HTTPException(status_code=400, detail="No valid lead IDs found")

    # Update the outreach_targets in the state
    state["outreach_targets"] = outreach_targets
    state["current_task"] = "outreach_targets_selected"
    campaign["state"] = state

    return {
        "status": "success",
        "message": f"Set {len(outreach_targets)} leads as outreach targets",
        "targets": [{"lead_id": t.lead_id, "name": t.name} for t in outreach_targets]
    }

@app.get("/campaigns/{campaign_id}/leads")
async def get_campaign_leads(
    campaign_id: str,
    status: Optional[str] = None,
    platform: Optional[str] = None,
    min_audience: Optional[int] = None,
    search: Optional[str] = None
):
    """Get filtered leads/prospects from a campaign"""
    if campaign_id not in campaign_registry:
        raise HTTPException(status_code=404, detail="Campaign not found")

    campaign = campaign_registry[campaign_id]
    state = campaign.get("state", {})
    prospects = state.get("prospects", [])

    # Apply filters
    filtered_prospects = prospects

    if status:
        filtered_prospects = [
            p for p in filtered_prospects
            if (hasattr(p, "status") and hasattr(p.status, "value") and p.status.value == status) or
               (isinstance(p, dict) and p.get("status") == status)
        ]

    if platform:
        filtered_prospects = [
            p for p in filtered_prospects
            if (hasattr(p, "platform") and p.platform == platform) or
               (isinstance(p, dict) and p.get("platform") == platform)
        ]

    if min_audience:
        filtered_prospects = [
            p for p in filtered_prospects
            if (hasattr(p, "audience_size") and p.audience_size >= min_audience) or
               (isinstance(p, dict) and p.get("audience_size", 0) >= min_audience)
        ]

    if search:
        search_lower = search.lower()
        filtered_prospects = [
            p for p in filtered_prospects
            if (hasattr(p, "name") and search_lower in p.name.lower()) or
               (hasattr(p, "notes") and p.notes and search_lower in p.notes.lower()) or
               (isinstance(p, dict) and
                ((p.get("name", "") and search_lower in p.get("name", "").lower()) or
                 (p.get("notes", "") and search_lower in p.get("notes", "").lower())))
        ]

    # Convert to serializable format
    result = []
    for prospect in filtered_prospects:
        if hasattr(prospect, "lead_id"):
            # AffiliateLead object
            result.append({
                "lead_id": prospect.lead_id,
                "name": prospect.name,
                "platform": prospect.platform,
                "audience_size": prospect.audience_size,
                "engagement_rate": prospect.engagement_rate,
                "content_quality_score": prospect.content_quality_score,
                "relevance_score": prospect.relevance_score,
                "status": prospect.status.value if hasattr(prospect.status, "value") else str(prospect.status),
                "contact_info": prospect.contact_info,
                "outreach_history": prospect.outreach_history,
                "notes": prospect.notes
            })
        else:
            # Already a dict
            result.append(prospect)

    return result

@app.get("/campaigns/{campaign_id}/affiliates")
async def get_campaign_affiliates(campaign_id: str):
    """Get active affiliates from a campaign"""
    if campaign_id not in campaign_registry:
        raise HTTPException(status_code=404, detail="Campaign not found")

    campaign = campaign_registry[campaign_id]
    state = campaign.get("state", {})
    affiliates = state.get("active_affiliates", [])

    # Convert to serializable format
    result = []
    for affiliate in affiliates:
        if hasattr(affiliate, "lead_id"):
            # AffiliateLead object
            result.append({
                "lead_id": affiliate.lead_id,
                "name": affiliate.name,
                "platform": affiliate.platform,
                "audience_size": affiliate.audience_size if hasattr(affiliate, "audience_size") else None,
                "status": affiliate.status.value if hasattr(affiliate.status, "value") else str(affiliate.status),
                "contact_info": affiliate.contact_info
            })
        else:
            # Already a dict
            result.append(affiliate)

    return result

@app.get("/campaigns/{campaign_id}/commissions")
async def get_campaign_commissions(campaign_id: str, status: Optional[str] = None):
    """Get commissions from a campaign with optional status filter"""
    if campaign_id not in campaign_registry:
        raise HTTPException(status_code=404, detail="Campaign not found")

    campaign = campaign_registry[campaign_id]
    state = campaign.get("state", {})
    commissions = state.get("commissions_log", [])

    # Apply status filter if provided
    if status:
        filtered_commissions = []
        for commission in commissions:
            commission_status = None
            if hasattr(commission, "status") and hasattr(commission.status, "value"):
                commission_status = commission.status.value
            elif isinstance(commission, dict) and "status" in commission:
                commission_status = commission["status"]

            if commission_status == status:
                filtered_commissions.append(commission)
        commissions = filtered_commissions

    # Convert to serializable format
    result = []
    for commission in commissions:
        if hasattr(commission, "commission_id"):
            # Commission object
            result.append({
                "commission_id": commission.commission_id,
                "affiliate_id": commission.affiliate_id,
                "sale_amount": commission.sale_amount,
                "commission_rate": commission.commission_rate,
                "commission_amount": commission.commission_amount,
                "sale_date": commission.sale_date,
                "status": commission.status.value if hasattr(commission.status, "value") else str(commission.status),
                "product_id": commission.product_id,
                "customer_id": commission.customer_id
            })
        else:
            # Already a dict
            result.append(commission)

    return result

async def run_campaign_cycle(campaign_id: str):
    """
    Run a single cycle of the campaign workflow.
    This function is called by the background tasks.
    """
    if campaign_id not in campaign_registry:
        print(f"Campaign {campaign_id} not found in registry.")
        return

    campaign = campaign_registry[campaign_id]
    campaign["status"] = "running"
    campaign["last_run"] = datetime.now(timezone.utc).isoformat()

    try:
        # Get current state
        current_state = campaign["state"]

        # Run the workflow
        # In a real LangGraph implementation, this would call graph.invoke()
        system = campaign["system"]
        new_state = await system.ainvoke(current_state, config={"configurable": {"thread_id": campaign_id}})

        # Update the campaign state
        campaign["state"] = new_state
        campaign["status"] = "idle"

        print(f"Campaign {campaign_id} cycle completed successfully.")

    except Exception as e:
        print(f"Error running campaign {campaign_id}: {str(e)}")
        campaign["status"] = "error"
        if "state" in campaign:
            campaign["state"]["last_error"] = str(e)

if __name__ == "__main__":
    # Run the server
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
