import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from ..core.state import AffiliateLead, AffiliateSystemState, LeadStatus

class OutreachAgent:
    """
    Agent responsible for crafting and sending personalized outreach messages
    to selected prospects.
    """
    def __init__(self,
                 llm_client: Any,  # Using Any for type flexibility
                 composio_client: Any,
                 outreach_config: Dict[str, Any]):
        """
        Initializes the OutreachAgent.

        Args:
            llm_client: Client for interacting with the Language Model.
            composio_client: Client for Composio tool integration.
            outreach_config: Configuration for outreach, e.g.,
                             {
                                 "outreach_method": "email",
                                 "email_subject_template": "Collaboration: {LEAD_NAME} x OurBrand",
                                 "message_templates": { "default": "Hi {LEAD_NAME}, ..."},
                                 "max_outreach_per_run": 5
                             }
        """
        self.llm_client = llm_client
        self.composio_client = composio_client
        self.outreach_config = outreach_config

    async def _generate_personalized_message(self, lead: AffiliateLead) -> str:
        """
        Generates a personalized outreach message for a given lead using an LLM.

        Args:
            lead: The AffiliateLead object for whom to generate the message.

        Returns:
            A string containing the personalized message.
        """
        print(f"OutreachAgent: Generating personalized message for {lead.name}...")

        # Get base template from config
        template_key = "default"  # Could be based on lead.platform, audience size, etc.
        base_template = self.outreach_config.get("message_templates", {}).get(
            template_key,
            "Hi {LEAD_NAME}, we noticed your work on {LEAD_PLATFORM} and are impressed. We'd like to discuss a potential collaboration with OurBrand."
        )

        # Fill in basic template variables
        basic_message = base_template.format(LEAD_NAME=lead.name, LEAD_PLATFORM=lead.platform)

        # Create prompt for LLM personalization
        prompt = (
            f"Generate a personalized outreach message for an affiliate marketing program.\n\n"
            f"Prospect Information:\n"
            f"- Name: {lead.name}\n"
            f"- Platform: {lead.platform}\n"
            f"- Audience Size: {lead.audience_size}\n"
            f"- Content Quality Score: {lead.content_quality_score}/10\n"
            f"- Relevance Score: {lead.relevance_score}/10\n"
            f"- Notes: {lead.notes if lead.notes else 'No additional information'}\n\n"
            f"Base Message Template:\n{basic_message}\n\n"
            f"Instructions:\n"
            f"1. Create a highly personalized message that references specific aspects of their content\n"
            f"2. Highlight our generous commission structure (70% commission)\n"
            f"3. Mention our product's relevance to their audience\n"
            f"4. Keep the tone professional but friendly\n"
            f"5. Include a clear call-to-action\n"
            f"6. Sign off from 'The OurBrand Team'\n"
            f"7. Keep the message concise (150-200 words)"
        )

        try:
            # Call LLM for personalization
            llm_response = await self.llm_client.ainvoke(prompt)

            # Process LLM response
            personalized_message = basic_message # Fallback
            if hasattr(llm_response, 'content') and isinstance(llm_response.content, str):
                personalized_message = llm_response.content
                if not personalized_message.strip(): # If LLM returns empty string
                    print(f"OutreachAgent: LLM returned empty message for {lead.name}. Using basic template.")
                    personalized_message = basic_message
            elif isinstance(llm_response, str): # Should ideally be AIMessage, but handle direct string
                personalized_message = llm_response
                if not personalized_message.strip():
                    print(f"OutreachAgent: LLM returned empty string (direct str) for {lead.name}. Using basic template.")
                    personalized_message = basic_message
            else:
                # Unexpected response format - use the basic filled template
                print(f"OutreachAgent: Unexpected LLM response format for {lead.name}. Type: {type(llm_response)}. Using basic template.")

            return personalized_message

        except Exception as e:
            print(f"OutreachAgent: Error generating message for {lead.name}: {e}")
            # Fallback to basic template
            return basic_message

    async def execute_outreach(self, state: AffiliateSystemState) -> AffiliateSystemState:
        """
        Executes the outreach process for leads marked as outreach_targets.

        Args:
            state: The current affiliate system state.

        Returns:
            The updated affiliate system state.
        """
        print("OutreachAgent: Starting outreach execution...")

        # Get outreach targets from state
        outreach_targets = state.outreach_targets
        if not outreach_targets:
            print("OutreachAgent: No targets selected for outreach.")
            state.current_task_description = "Outreach: No targets."
            return state

        # Get configuration parameters
        max_outreach = self.outreach_config.get("max_outreach_per_run", len(outreach_targets))
        outreach_method = self.outreach_config.get("outreach_method", "email")
        subject_template = self.outreach_config.get("email_subject_template", "Collaboration Opportunity with OurBrand")

        # Track outreach results
        contacted_count = 0
        failed_count = 0
        skipped_count = 0

        # Create a mapping of lead_id to prospect for updating later
        prospects_map = {p.lead_id: p for p in state.prospects}

        # Process each target up to the maximum limit
        for lead in outreach_targets:
            if contacted_count >= max_outreach:
                print(f"OutreachAgent: Reached max outreach limit for this run ({max_outreach}).")
                break

            # Skip leads that have already been contacted
            if lead.status == LeadStatus.CONTACTED or lead.status == LeadStatus.CONVERTED:
                print(f"OutreachAgent: Skipping {lead.name}, already contacted or converted.")
                skipped_count += 1
                continue

            print(f"OutreachAgent: Processing outreach for {lead.name} ({lead.lead_id}).")

            # Generate personalized message
            message_body = await self._generate_personalized_message(lead)

            # Create subject line
            subject = subject_template.format(LEAD_NAME=lead.name, LEAD_PLATFORM=lead.platform)

            # Send outreach based on configured method
            success = False
            outreach_result = {}

            # --- MOCK OUTREACH LOGIC ---
            print(f"OutreachAgent: Simulating {outreach_method} outreach for {lead.name} ({lead.lead_id}).")
            await asyncio.sleep(0.1) # Simulate async operation

            if lead.lead_id == "yt_ai_channel_1": # Specific mock prospect for conversion
                print(f"OutreachAgent: Mock converting lead {lead.name} ({lead.lead_id}).")
                success = True
                lead.status = LeadStatus.CONVERTED # Simulate conversion
                outreach_result = {
                    "channel": outreach_method,
                    "recipient": lead.contact_info.get("email", "mock_contact"),
                    "message_id": f"mock_msg_id_{lead.lead_id}"
                }
            elif outreach_method == "email" and lead.contact_info.get("email"):
                print(f"OutreachAgent: Mock contacting lead {lead.name} ({lead.lead_id}) via email.")
                success = True # Simulate successful contact for other emailable leads
                lead.status = LeadStatus.CONTACTED
                outreach_result = {
                    "channel": "email",
                    "recipient": lead.contact_info.get("email"),
                    "message_id": f"mock_msg_id_{lead.lead_id}"
                }
            elif outreach_method == "twitter" and lead.contact_info.get("twitter_handle"):
                 print(f"OutreachAgent: Mock contacting lead {lead.name} ({lead.lead_id}) via Twitter.")
                 success = True
                 lead.status = LeadStatus.CONTACTED
                 outreach_result = {
                     "channel": "twitter",
                     "recipient": lead.contact_info.get("twitter_handle"),
                     "message_id": f"mock_msg_id_{lead.lead_id}"
                 }
            else: # Simulate skipped if no valid contact info for the chosen method
                print(f"OutreachAgent: Mock skipping outreach for {lead.name} due to missing contact info for {outreach_method} or unhandled mock case.")
                lead.notes = (lead.notes or "") + f"\nMock outreach skipped: No contact info for {outreach_method} or unhandled."
                success = False
                skipped_count +=1


            # Update lead with outreach result
            if success:
                # For CONVERTED leads, a "sent" history might not be as relevant as a "converted" event,
                # but for simplicity, we'll use the existing structure.
                # If it's converted, the CRMAgent will handle moving it to active_affiliates.
                print(f"OutreachAgent: Successfully simulated {outreach_method} outreach to {lead.name} (Status: {lead.status.value}).")
                lead.outreach_history.append({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "type": outreach_method,
                    "subject": subject if outreach_method == "email" else None,
                    "message_excerpt": message_body[:100] + "..." if len(message_body) > 100 else message_body,
                    "status": "simulated_sent_or_converted",
                    "details": outreach_result
                })
                contacted_count += 1 # Count converted as contacted for this metric

                # Update in the main prospects list
                if lead.lead_id in prospects_map:
                    prospects_map[lead.lead_id] = lead
            elif not success and skipped_count == 0: # Only count as failed if not explicitly skipped
                print(f"OutreachAgent: Mock failed to send {outreach_method} outreach to {lead.name}.")
                lead.notes = (lead.notes or "") + f"\nMock outreach failed."
                failed_count += 1

                # Update in the main prospects list
                if lead.lead_id in prospects_map:
                    prospects_map[lead.lead_id] = lead
            # --- END MOCK OUTREACH LOGIC ---

            # Original exception handling for the loop, not for Composio calls (which are now mocked)
            # This is intentionally left outside the mock logic block for any other unforeseen issues.
            # However, since all external calls are mocked, this might not be strictly necessary anymore.
            # For robustness, we can keep a general try-except for the lead processing loop.
            # The previous try-except that wrapped specific Composio calls is removed.
            # No, actually, the loop should handle its own exceptions per lead if _generate_personalized_message fails.
            # The code structure outside the MOCK block handles the try-except for the _generate_personalized_message
            # and then updates based on `success`. The mock block above now sets `success`.
            # So, the outer try-except for the whole lead processing loop is no longer needed in the same way.
            # Let's remove the broad try-except that was previously for Composio calls.

                # Update in the main prospects list
                if lead.lead_id in prospects_map:
                    prospects_map[lead.lead_id] = lead

        # Update state with modified leads
        state.prospects = list(prospects_map.values())

        # Clear outreach targets after processing
        state.outreach_targets = []

        # Update task description
        state.current_task_description = (
            f"Outreach: Contacted {contacted_count} leads, "
            f"failed {failed_count}, skipped {skipped_count}."
        )

        print(f"OutreachAgent: Finished outreach execution. Contacted: {contacted_count}, Failed: {failed_count}, Skipped: {skipped_count}")
        return state
