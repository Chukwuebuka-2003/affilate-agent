import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from ..core.state import AffiliateLead, AffiliateSystemState, LeadStatus

class SocialScoutAgent:
    """
    Agent responsible for identifying potential affiliate partners
    by scanning social media and other platforms.
    """
    def __init__(self,
                 llm_client: Any,  # Using Any for type flexibility
                 composio_client: Any,
                 scouting_config: Dict[str, Any]):
        """
        Initializes the SocialScoutAgent.

        Args:
            llm_client: Client for interacting with the Language Model.
            composio_client: Client for Composio tool integration.
            scouting_config: Configuration for scouting, e.g.,
                             {"platforms": ["youtube", "twitter"], "keywords": ["ai", "devrel"], "min_audience_size": 1000}
        """
        self.llm_client = llm_client
        self.composio_client = composio_client
        self.scouting_config = scouting_config

    async def _fetch_platform_data(self, platform: str, keyword: str) -> List[Dict[str, Any]]:
        """
        Fetches data from a specific platform using Composio.
        """
        print(f"SocialScoutAgent: Scouting on {platform} for keyword: {keyword} (using mock data)...")

        mock_prospects = []
        # Only add mock data for specific platform/keyword combinations to simulate variability
        if platform == "youtube" and "AI" in keyword:
            mock_prospects.extend([
                {
                    "id": "yt_ai_channel_1", "name": "AI Insights Hub", "platform": "youtube",
                    "audience_size": 150000, "engagement_rate": 0.05,
                    "description": "Deep dives into AI research and applications.",
                    "contact_info": {"email": "ai.insights@example.com"}
                },
                {
                    "id": "yt_ai_channel_2", "name": "ML For Everyone", "platform": "youtube",
                    "audience_size": 75000, "engagement_rate": 0.03,
                    "description": "Making machine learning accessible to all.",
                    "contact_info": {"email": "ml.everyone@example.com"}
                }
            ])
        elif platform == "twitter" and "SaaS" in keyword:
            mock_prospects.extend([
                {
                    "id": "tw_saas_guru_1", "name": "SaaS Guru", "platform": "twitter",
                    "audience_size": 25000, "engagement_rate": 0.02,
                    "description": "Latest trends and reviews in the SaaS world.",
                    "contact_info": {"twitter_handle": "@saasguru"}
                },
                {
                    "id": "tw_saas_reviewer_2", "name": "CloudReviewer", "platform": "twitter",
                    "audience_size": 500, "engagement_rate": 0.01, # Example below min_audience_size
                    "description": "Honest SaaS reviews.",
                    "contact_info": {"twitter_handle": "@cloudreviewer"}
                }
            ])

        # Simulate a small delay as if fetching data
        await asyncio.sleep(0.1)

        print(f"SocialScoutAgent: Found {len(mock_prospects)} mock prospects on {platform} for {keyword}")
        return mock_prospects

    async def scout_prospects(self, state: AffiliateSystemState) -> AffiliateSystemState:
        """
        Scans platforms for potential affiliates based on defined criteria.

        Args:
            state: The current affiliate system state.

        Returns:
            The updated affiliate system state with new prospects.
        """
        print("SocialScoutAgent: Starting prospect scouting...")
        platforms = self.scouting_config.get("platforms", ["youtube", "twitter", "linkedin", "instagram"])
        keywords = self.scouting_config.get("keywords", ["AI tools", "SaaS review"])
        min_audience_size = self.scouting_config.get("min_audience_size", 1000)

        all_raw_prospects: List[Dict[str, Any]] = []

        # Fetch prospects from each platform and keyword combination
        for platform in platforms:
            for keyword in keywords:
                platform_prospects = await self._fetch_platform_data(platform, keyword)
                all_raw_prospects.extend(platform_prospects)

        print(f"SocialScoutAgent: Found {len(all_raw_prospects)} raw prospects before filtering.")

        # Filter by minimum audience size
        filtered_raw_prospects = [
            p for p in all_raw_prospects
            if p.get("audience_size", 0) >= min_audience_size
        ]
        print(f"SocialScoutAgent: {len(filtered_raw_prospects)} prospects after min_audience_size filter.")

        if not filtered_raw_prospects:
            print("SocialScoutAgent: No prospects found meeting initial criteria.")
            # state.prospects is already initialized as an empty list by Pydantic's default_factory
            return state

        # Score prospects using LLM
        scored_prospects = await self._score_prospects(filtered_raw_prospects)

        # Update state with new prospects, avoiding duplicates
        existing_lead_ids = {lead.lead_id for lead in state.prospects}
        new_leads = [lead for lead in scored_prospects if lead.lead_id not in existing_lead_ids]

        state.prospects.extend(new_leads) # Directly extend the list on the Pydantic model
        state.current_task_description = f"Scouted {len(new_leads)} new prospects. Total prospects: {len(state.prospects)}."
        print(f"SocialScoutAgent: Added {len(new_leads)} new prospects. Total prospects now: {len(state.prospects)}.")
        return state

    async def _score_prospects(self, raw_prospects: List[Dict[str, Any]]) -> List[AffiliateLead]:
        """
        Scores raw prospect data using an LLM based on predefined criteria.

        Args:
            raw_prospects: A list of dictionaries, each representing a raw prospect.
                           Expected keys: 'id', 'name', 'platform', 'audience_size',
                                          'engagement_rate', 'description', 'contact_info'.

        Returns:
            A list of AffiliateLead objects.
        """
        print(f"SocialScoutAgent: Scoring {len(raw_prospects)} prospects...")
        scored_leads: List[AffiliateLead] = []
        scoring_criteria = self.scouting_config.get("scoring_criteria",
            "Evaluate the prospect based on content quality related to our niche (e.g., AI, SaaS, productivity) "
            "and relevance of their audience to our target customers. "
            "Provide a content_quality_score (0-10) and relevance_score (0-10)."
        )

        for prospect_data in raw_prospects:
            # Prepare data for scoring
            name = prospect_data.get('name', 'Unknown Prospect')
            platform = prospect_data.get('platform', 'Unknown Platform')
            audience_size = prospect_data.get('audience_size', 0)
            engagement_rate = prospect_data.get('engagement_rate', 0.0)
            description = prospect_data.get('description', 'No description available')

            # Construct prompt for LLM
            prompt = (
                f"Prospect Profile:\n"
                f"Name: {name}\n"
                f"Platform: {platform}\n"
                f"Audience Size: {audience_size}\n"
                f"Engagement Rate: {engagement_rate:.3f}\n"
                f"Description/Bio: {description}\n\n"
                f"Scoring Criteria: {scoring_criteria}\n\n"
                f"Output your evaluation as a JSON object with keys: "
                f"'content_quality_score' (float), 'relevance_score' (float)."
            )

            content_quality = 0.0
            relevance = 0.0
            prospect_id = prospect_data.get("id")

            # Check if this is a known mock prospect to assign hardcoded scores
            if prospect_id == "yt_ai_channel_1":
                print(f"SocialScoutAgent: Assigning mock scores for {name}")
                content_quality = 8.0
                relevance = 9.0
            elif prospect_id == "yt_ai_channel_2":
                print(f"SocialScoutAgent: Assigning mock scores for {name}")
                content_quality = 7.0
                relevance = 7.5
            elif prospect_id == "tw_saas_guru_1": # This one is also in mock_prospects
                print(f"SocialScoutAgent: Assigning mock scores for {name}")
                content_quality = 8.5
                relevance = 8.0
            elif prospect_id == "tw_saas_reviewer_2": # This one has low audience, might not reach here
                print(f"SocialScoutAgent: Assigning mock scores for {name}")
                content_quality = 6.0
                relevance = 6.5
            else:
                # If not a known mock prospect, call LLM
                try:
                    print(f"SocialScoutAgent: Calling LLM to score prospect {name}")
                    llm_response = await self.llm_client.ainvoke(prompt)

                    # Process LLM response - handle different response formats
                    if isinstance(llm_response, dict) and "error" not in llm_response:
                        content_quality = float(llm_response.get("content_quality_score", 0.0))
                        relevance = float(llm_response.get("relevance_score", 0.0))
                    elif hasattr(llm_response, 'content') and isinstance(llm_response.content, str): # AIMessage
                        # Try to extract JSON from AIMessage content string
                        try:
                            import json
                            # Find JSON-like content in the response
                            if "{" in llm_response.content and "}" in llm_response.content:
                                json_str = llm_response.content[llm_response.content.find("{"):llm_response.content.rfind("}")+1]
                                json_data = json.loads(json_str)
                                content_quality = float(json_data.get("content_quality_score", 0.0))
                                relevance = float(json_data.get("relevance_score", 0.0))
                            else: # If no JSON, assign default scores
                                print(f"SocialScoutAgent: LLM response for {name} did not contain JSON. Using default scores.")
                                content_quality = 5.0
                                relevance = 5.0
                        except Exception as e_parse:
                            print(f"SocialScoutAgent: Error parsing LLM (AIMessage) response as JSON for {name}: {e_parse}. Using default scores.")
                            content_quality = 5.0
                            relevance = 5.0
                    elif isinstance(llm_response, str): # Deprecated? but handle just in case
                         # Try to extract JSON from string response
                        try:
                            import json
                            # Find JSON-like content in the response
                            if "{" in llm_response and "}" in llm_response:
                                json_str = llm_response[llm_response.find("{"):llm_response.rfind("}")+1]
                                json_data = json.loads(json_str)
                                content_quality = float(json_data.get("content_quality_score", 0.0))
                                relevance = float(json_data.get("relevance_score", 0.0))
                            else: # If no JSON, assign default scores
                                print(f"SocialScoutAgent: LLM response for {name} was a string but did not contain JSON. Using default scores.")
                                content_quality = 5.0
                                relevance = 5.0
                        except Exception as e_parse_str:
                            print(f"SocialScoutAgent: Error parsing LLM (string) response as JSON for {name}: {e_parse_str}. Using default scores.")
                            content_quality = 5.0
                            relevance = 5.0
                    else:
                        print(f"SocialScoutAgent: Unexpected LLM response type for {name}: {type(llm_response)}. Using default scores.")
                        content_quality = 5.0
                        relevance = 5.0

                except Exception as e:
                    print(f"SocialScoutAgent: Error scoring prospect {name} with LLM: {e}. Using default scores.")
                    content_quality = 5.0  # Default score on error
                    relevance = 5.0    # Default score on error

            # Ensure contact_info is a dictionary
            contact_info = prospect_data.get("contact_info", {})
            if not isinstance(contact_info, dict):
                contact_info = {}

            # Create AffiliateLead object
            lead = AffiliateLead(
                lead_id=str(prospect_data.get("id", f"prospect_{platform}_{name}")),
                name=name,
                contact_info=contact_info,
                platform=platform,
                audience_size=int(audience_size),
                engagement_rate=float(engagement_rate),
                content_quality_score=content_quality,
                relevance_score=relevance,
                status=LeadStatus.NEW,
                notes=description[:200] if description else ""  # Truncate long descriptions
            )
            scored_leads.append(lead)
            print(f"SocialScoutAgent: Scored prospect {lead.name} - CQ: {content_quality}, Rel: {relevance}")

        # Sort leads by total score (quality + relevance)
        scored_leads.sort(key=lambda x: x.content_quality_score + x.relevance_score, reverse=True)
        return scored_leads
