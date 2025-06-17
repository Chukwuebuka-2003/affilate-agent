import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from ..core.state import AffiliateLead, AffiliateSystemState, LeadStatus

class CRMAgent:
    """
    Agent responsible for managing affiliate data in a CRM system.
    Creates/updates records for new affiliates and logs interactions.
    """
    def __init__(self,
                 composio_client: Any,  # Using Any for type flexibility
                 crm_config: Dict[str, Any]):
        """
        Initializes the CRMAgent.

        Args:
            composio_client: Client for Composio tool integration.
            crm_config: Configuration for CRM, e.g.,
                        {
                            "tool_id": "hubspot", # Composio tool identifier
                            "affiliate_status_field": "affiliate_status_custom_field",
                            "default_owner_id": "user_id_123"
                        }
        """
        self.composio_client = composio_client
        self.crm_config = crm_config

    async def manage_affiliate_data(self, state: AffiliateSystemState) -> AffiliateSystemState:
        """
        Manages affiliate data in the CRM.
        Focuses on leads that are CONTACTED, INTERESTED, or CONVERTED.

        Args:
            state: The current affiliate system state.

        Returns:
            The updated affiliate system state with CRM update status.
        """
        print("CRMAgent: Starting CRM data management...")

        # Get the CRM tool ID from config
        crm_tool_id = self.crm_config.get("tool_id", "hubspot")

        # Create a list of leads that need CRM updates
        # These are leads that have been contacted or have shown interest
        leads_to_sync = []

        # Include all active affiliates
        active_affiliate_ids = {aff.lead_id for aff in state.active_affiliates}
        newly_converted_leads_for_crm_sync = []
        remaining_prospects = []

        # Process prospects: identify conversions, build list of remaining prospects
        for lead in state.prospects:
            if lead.status == LeadStatus.CONVERTED:
                if lead.lead_id not in active_affiliate_ids:
                    print(f"CRMAgent: Adding {lead.name} ({lead.lead_id}) to active affiliates.")
                    state.active_affiliates.append(lead)
                    active_affiliate_ids.add(lead.lead_id) # Update set for immediate consistency
                    newly_converted_leads_for_crm_sync.append(lead) # Ensure fresh converts are synced
                # Converted leads are removed from the main prospects list
            else:
                remaining_prospects.append(lead)
        state.prospects = remaining_prospects

        # Build leads_to_sync:
        # 1. Freshly converted leads.
        # 2. Existing active affiliates (for ongoing updates, if any).
        # 3. Prospects that are CONTACTED or INTERESTED.

        leads_to_sync_map = {lead.lead_id: lead for lead in newly_converted_leads_for_crm_sync}

        for affiliate in state.active_affiliates:
            if affiliate.lead_id not in leads_to_sync_map:
                leads_to_sync_map[affiliate.lead_id] = affiliate

        for lead in state.prospects: # state.prospects is now filtered of CONVERTED leads
            if lead.status in [LeadStatus.CONTACTED, LeadStatus.INTERESTED]:
                if lead.lead_id not in leads_to_sync_map:
                    leads_to_sync_map[lead.lead_id] = lead

        leads_to_sync = list(leads_to_sync_map.values())

        if not leads_to_sync:
            print("CRMAgent: No leads found requiring CRM updates.")
            state.crm_update_status = "No leads to sync."
            return state

        print(f"CRMAgent: Found {len(leads_to_sync)} leads/affiliates requiring CRM updates/sync.")

        # Track synchronization results
        successful_syncs = 0
        failed_syncs = 0

        # Process each lead
        for lead in leads_to_sync:
            # Skip leads without email as most CRMs require it
            if not lead.contact_info.get("email"):
                print(f"CRMAgent: Skipping CRM sync for {lead.name} - no email address.")
                lead.notes = (lead.notes or "") + "\nCRM Sync skipped: No email."
                failed_syncs += 1
                continue

            # Prepare data for CRM record
            try:
                # Map lead data to CRM fields
                crm_data = await self._map_lead_to_crm_fields(lead, crm_tool_id)

                # Perform the CRM operation based on the tool
                if crm_tool_id == "hubspot":
                    await self._sync_to_hubspot(lead, crm_data)
                    successful_syncs += 1
                elif crm_tool_id == "salesforce":
                    await self._sync_to_salesforce(lead, crm_data)
                    successful_syncs += 1
                elif crm_tool_id == "zoho":
                    await self._sync_to_zoho(lead, crm_data)
                    successful_syncs += 1
                else:
                    # Generic CRM sync for other systems
                    success = await self._generic_crm_sync(lead, crm_data, crm_tool_id)
                    if success:
                        successful_syncs += 1
                    else:
                        failed_syncs += 1

            except Exception as e:
                print(f"CRMAgent: Error syncing {lead.name} to CRM: {e}")
                lead.notes = (lead.notes or "") + f"\nCRM Sync Error: {e}"
                failed_syncs += 1

        # Update state with sync status
        sync_status = f"CRM Sync: {successful_syncs} successful, {failed_syncs} failed."
        state.crm_update_status = sync_status
        current_desc = state.current_task_description if state.current_task_description is not None else ""
        state.current_task_description = f"{current_desc} {sync_status}"

        print(f"CRMAgent: {sync_status}")
        return state

    async def _map_lead_to_crm_fields(self, lead: AffiliateLead, crm_tool_id: str) -> Dict[str, Any]:
        """
        Maps lead data to CRM-specific fields.
        Different CRMs have different field structures.
        """
        # Common fields across most CRMs
        common_data = {
            "email": lead.contact_info.get("email"),
            "first_name": lead.name.split(" ")[0] if " " in lead.name else lead.name,
            "last_name": lead.name.split(" ")[-1] if " " in lead.name and len(lead.name.split(" ")) > 1 else "",
            "lead_source": "AI Affiliate Program",
            "status": lead.status.value,
            "lead_score": lead.content_quality_score + lead.relevance_score,
            "platform": lead.platform,
            "audience_size": lead.audience_size,
            "engagement_rate": lead.engagement_rate,
            "notes": lead.notes
        }

        # Add outreach history summary if available
        if lead.outreach_history:
            last_outreach = lead.outreach_history[-1]
            common_data["last_outreach_date"] = last_outreach.get("timestamp")
            common_data["last_outreach_channel"] = last_outreach.get("type")

        # CRM-specific mappings
        if crm_tool_id == "hubspot":
            return {
                "properties": {
                    "email": common_data["email"],
                    "firstname": common_data["first_name"],
                    "lastname": common_data["last_name"],
                    "lead_source": common_data["lead_source"],
                    self.crm_config.get("affiliate_status_field", "affiliate_status"): common_data["status"],
                    "lead_score": str(common_data["lead_score"]),
                    "platform": common_data["platform"],
                    "audience_size": str(common_data["audience_size"]),
                    "engagement_rate": str(common_data["engagement_rate"]),
                    "notes": common_data["notes"]
                }
            }
        elif crm_tool_id == "salesforce":
            return {
                "Email": common_data["email"],
                "FirstName": common_data["first_name"],
                "LastName": common_data["last_name"],
                "LeadSource": common_data["lead_source"],
                self.crm_config.get("affiliate_status_field", "Affiliate_Status__c"): common_data["status"],
                "Lead_Score__c": common_data["lead_score"],
                "Platform__c": common_data["platform"],
                "Audience_Size__c": common_data["audience_size"],
                "Engagement_Rate__c": common_data["engagement_rate"],
                "Description": common_data["notes"]
            }
        else:
            # Generic mapping for other CRMs
            return common_data

    async def _sync_to_hubspot(self, lead: AffiliateLead, crm_data: Dict[str, Any]) -> bool:
        """
        Synchronizes a lead to HubSpot CRM.
        """
        try:
            # MOCK HubSpot Sync
            print(f"CRMAgent: Simulating HubSpot sync for {lead.name}...")
            await asyncio.sleep(0.05) # Simulate async operation
            print(f"CRMAgent: Successfully mock-synced {lead.name} to HubSpot. Mock Contact ID: mock_hs_{lead.lead_id}")
            lead.notes = (lead.notes or "") + f"\nMock Synced to HubSpot: {datetime.now(timezone.utc).isoformat()}"
            return True
        except Exception as e:
            print(f"CRMAgent: Exception during mock HubSpot sync for {lead.name}: {e}")
            lead.notes = (lead.notes or "") + f"\nMock HubSpot sync exception: {e}"
            return False

    async def _sync_to_salesforce(self, lead: AffiliateLead, crm_data: Dict[str, Any]) -> bool:
        """
        Synchronizes a lead to Salesforce CRM.
        """
        try:
            # MOCK Salesforce Sync
            print(f"CRMAgent: Simulating Salesforce sync for {lead.name}...")
            await asyncio.sleep(0.05) # Simulate async operation
            print(f"CRMAgent: Successfully mock-synced {lead.name} to Salesforce. Mock Contact ID: mock_sf_{lead.lead_id}")
            lead.notes = (lead.notes or "") + f"\nMock Synced to Salesforce: {datetime.now(timezone.utc).isoformat()}"
            return True
        except Exception as e:
            print(f"CRMAgent: Exception during mock Salesforce sync for {lead.name}: {e}")
            lead.notes = (lead.notes or "") + f"\nMock Salesforce sync exception: {e}"
            return False

    async def _sync_to_zoho(self, lead: AffiliateLead, crm_data: Dict[str, Any]) -> bool:
        """
        Synchronizes a lead to Zoho CRM.
        """
        # MOCK Zoho Sync
        print(f"CRMAgent: Simulating Zoho CRM sync for {lead.name}...")
        await asyncio.sleep(0.05) # Simulate async operation
        print(f"CRMAgent: Successfully mock-synced {lead.name} to Zoho. Mock Contact ID: mock_zoho_{lead.lead_id}")
        lead.notes = (lead.notes or "") + f"\nMock Synced to Zoho: {datetime.now(timezone.utc).isoformat()}"
        return True

    async def _generic_crm_sync(self, lead: AffiliateLead, crm_data: Dict[str, Any], crm_tool_id: str) -> bool:
        """
        Generic synchronization for other CRM systems.
        """
        try:
            # MOCK Generic CRM Sync
            print(f"CRMAgent: Simulating generic CRM sync for {lead.name} to {crm_tool_id}...")
            await asyncio.sleep(0.05) # Simulate async operation
            print(f"CRMAgent: Successfully mock-synced {lead.name} to {crm_tool_id}. Mock Record ID: mock_generic_{lead.lead_id}")
            lead.notes = (lead.notes or "") + f"\nMock Synced to {crm_tool_id}: {datetime.now(timezone.utc).isoformat()}"
            return True
        except Exception as e:
            print(f"CRMAgent: Exception during mock generic CRM sync for {lead.name} to {crm_tool_id}: {e}")
            lead.notes = (lead.notes or "") + f"\nMock {crm_tool_id} sync exception: {e}"
            return False
