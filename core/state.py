from typing import List, Dict, TypedDict, Optional, Any
from enum import Enum
from pydantic import BaseModel, Field

class LeadStatus(Enum):
    """
    Enumeration of possible lead statuses in the affiliate system.
    """
    NEW = "NEW"                     # Lead identified but not contacted
    CONTACTED = "CONTACTED"         # Outreach has been sent
    INTERESTED = "INTERESTED"       # Lead has responded positively
    NOT_INTERESTED = "NOT_INTERESTED"  # Lead has declined
    CONVERTED = "CONVERTED"         # Lead has become an active affiliate

class AffiliateLead(BaseModel):
    """
    Represents a potential affiliate lead.
    """
    lead_id: str
    name: str
    contact_info: Dict[str, str] # e.g., {"email": "...", "social_media_profile": "..."}
    platform: str # e.g., "YouTube", "Instagram", "Blog"
    audience_size: int
    engagement_rate: float
    content_quality_score: float
    relevance_score: float
    status: LeadStatus = LeadStatus.NEW
    outreach_history: List[Dict[str, Any]] = Field(default_factory=list)
    notes: Optional[str] = None

    def __repr__(self):
        return (f"AffiliateLead(lead_id='{self.lead_id}', name='{self.name}', "
                f"platform='{self.platform}', status='{self.status.value}')")

class CommissionStatus(Enum):
    """
    Enumeration of possible commission statuses in the affiliate system.
    """
    PENDING = "PENDING"       # Commission recorded but not yet approved
    APPROVED = "APPROVED"     # Commission approved for payment
    PAID = "PAID"             # Commission has been paid
    REJECTED = "REJECTED"     # Commission has been rejected

class Commission(BaseModel):
    """
    Represents a commission earned by an affiliate.
    """
    commission_id: str
    affiliate_id: str # Corresponds to a converted AffiliateLead's ID or a dedicated affiliate ID
    sale_amount: float
    commission_rate: float
    commission_amount: float
    sale_date: str # ISO format date string
    status: CommissionStatus = CommissionStatus.PENDING
    product_id: Optional[str] = None
    customer_id: Optional[str] = None

    def __repr__(self):
        return (f"Commission(commission_id='{self.commission_id}', affiliate_id='{self.affiliate_id}', "
                f"amount={self.commission_amount}, status='{self.status.value}')")

class AffiliateSystemState(BaseModel):
    """
    Represents the overall state of the affiliate system.
    This will be passed around between nodes in the LangGraph.
    """
    prospects: List[AffiliateLead] = Field(default_factory=list)  # Leads identified by the SocialScoutAgent
    outreach_targets: List[AffiliateLead] = Field(default_factory=list)  # Prospects selected for outreach
    active_affiliates: List[AffiliateLead] = Field(default_factory=list)  # Leads that have been converted to affiliates
    commissions_log: List[Commission] = Field(default_factory=list)  # Log of all commissions
    crm_update_status: Optional[str] = None  # Status of the last CRM update
    last_error: Optional[str] = None  # To store any error messages during graph execution
    current_task_description: Optional[str] = None  # Describes the current high-level task
    campaign_performance_report: Optional[Dict[str, Any]] = None  # Report from analyze_performance
    current_task: Optional[str] = None  # Current task in the workflow
