import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone, timedelta
import json
from ..core.state import AffiliateSystemState, LeadStatus, CommissionStatus

class PerformanceAgent:
    """
    Agent responsible for analyzing system performance and generating
    optimization suggestions for the affiliate marketing system.
    """
    def __init__(self,
                 llm_client: Any,  # Using Any for type flexibility
                 composio_client: Any,
                 performance_config: Dict[str, Any]):
        """
        Initializes the PerformanceAgent.

        Args:
            llm_client: Client for interacting with the Language Model.
            composio_client: Client for Composio tool integration.
            performance_config: Configuration for performance analysis, e.g.,
                               {
                                   "analysis_period_days": 30,
                                   "report_metrics": ["conversion_rate", "epc", "roi"],
                                   "alert_thresholds": {
                                       "low_conversion_rate": 0.05,
                                       "low_epc": 0.5
                                   }
                               }
        """
        self.llm_client = llm_client
        self.composio_client = composio_client
        self.performance_config = performance_config

    async def _calculate_key_metrics(self, state: AffiliateSystemState) -> Dict[str, Any]:
        """
        Calculates key performance metrics from the system state.
        """
        # Set time range for analysis
        analysis_period_days = self.performance_config.get("analysis_period_days", 30)
        now = datetime.now(timezone.utc)
        analysis_start_date = now - timedelta(days=analysis_period_days)

        # Extract data from state for the analysis period
        prospects = state.prospects
        active_affiliates = state.active_affiliates
        commissions = [c for c in state.commissions_log
                      if datetime.fromisoformat(c.sale_date) > analysis_start_date]

        # Calculate prospect metrics
        total_prospects = len(prospects)
        contacted_prospects = sum(1 for p in prospects if p.status == LeadStatus.CONTACTED)
        converted_prospects = sum(1 for p in prospects if p.status == LeadStatus.CONVERTED)

        # Calculate conversion metrics
        outreach_conversion_rate = 0
        if contacted_prospects > 0:
            outreach_conversion_rate = converted_prospects / contacted_prospects

        # Calculate affiliate performance metrics
        total_commissions = sum(c.commission_amount for c in commissions)
        total_sales = sum(c.sale_amount for c in commissions)

        # Calculate EPC (Earnings Per Click) if available
        # In a real system, you'd track clicks in the state
        mock_total_clicks = 10000  # Mocked value
        epc = 0
        if mock_total_clicks > 0:
            epc = total_commissions / mock_total_clicks

        # Calculate ROI (assumes some cost for the affiliate program)
        # In a real system, you'd track program costs
        mock_program_cost = 5000  # Mocked value
        roi = 0
        if mock_program_cost > 0:
            roi = (total_sales - mock_program_cost) / mock_program_cost

        # Get top performing affiliates
        affiliate_performance = {}
        for commission in commissions:
            if commission.affiliate_id not in affiliate_performance:
                affiliate_performance[commission.affiliate_id] = 0
            affiliate_performance[commission.affiliate_id] += commission.commission_amount

        top_affiliates = sorted(affiliate_performance.items(), key=lambda x: x[1], reverse=True)[:5]

        # Compile metrics
        metrics = {
            "analysis_period_days": analysis_period_days,
            "analysis_start_date": analysis_start_date.isoformat(),
            "analysis_end_date": now.isoformat(),
            "prospect_metrics": {
                "total_prospects": total_prospects,
                "contacted_prospects": contacted_prospects,
                "converted_prospects": converted_prospects,
                "outreach_conversion_rate": outreach_conversion_rate
            },
            "financial_metrics": {
                "total_commissions": total_commissions,
                "total_sales": total_sales,
                "epc": epc,
                "roi": roi
            },
            "top_affiliates": [
                {"affiliate_id": aff_id, "earnings": earnings}
                for aff_id, earnings in top_affiliates
            ]
        }

        return metrics

    async def _generate_optimizations(self, metrics: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Uses an LLM to generate optimization suggestions based on performance metrics.
        """
        metrics_json = json.dumps(metrics, indent=2)

        prompt = (
            f"Analyze these performance metrics for an AI affiliate marketing system:\n\n"
            f"{metrics_json}\n\n"
            f"Based on these metrics, provide specific optimization suggestions to improve: "
            f"1. Prospect conversion rate\n"
            f"2. Affiliate earnings (EPC)\n"
            f"3. Overall ROI\n\n"
            f"For each suggestion, provide a clear action, expected impact, and implementation difficulty (easy/medium/hard).\n"
            f"Format your response as a JSON list of suggestions, each with 'action', 'impact', and 'difficulty' keys."
        )

        try:
            llm_response = await self.llm_client.ainvoke(prompt)

            # Parse the response to ensure it's valid JSON
            if isinstance(llm_response, str):
                # Extract JSON from text response if needed
                if "```json" in llm_response:
                    json_str = llm_response.split("```json")[1].split("```")[0].strip()
                    optimizations = json.loads(json_str)
                else:
                    # Attempt to parse the entire response as JSON
                    optimizations = json.loads(llm_response)
            elif isinstance(llm_response, list):
                # LLM already returned parsed JSON
                optimizations = llm_response
            elif isinstance(llm_response, dict) and "suggestions" in llm_response:
                # LLM returned a dict with suggestions key
                optimizations = llm_response["suggestions"]
            else:
                # Fallback - provide basic suggestions
                optimizations = [
                    {
                        "action": "Improve outreach message personalization",
                        "impact": "Could increase conversion rate by 20%",
                        "difficulty": "medium"
                    },
                    {
                        "action": "Optimize commission structure for top performers",
                        "impact": "Could increase sales from top affiliates by 15%",
                        "difficulty": "easy"
                    }
                ]

            return optimizations

        except Exception as e:
            print(f"PerformanceAgent: Error generating optimizations: {e}")
            # Return basic fallback suggestions
            return [
                {
                    "action": "Improve prospect targeting criteria",
                    "impact": "Better lead quality and higher conversion rates",
                    "difficulty": "medium"
                },
                {
                    "action": "Implement affiliate tiering with bonus incentives",
                    "impact": "Motivate top performers to drive more sales",
                    "difficulty": "easy"
                }
            ]

    async def _detect_anomalies(self, metrics: Dict[str, Any]) -> List[Dict[str, str]]:
        """
        Detects performance anomalies based on thresholds and historical data.
        """
        anomalies = []
        thresholds = self.performance_config.get("alert_thresholds", {})

        # Check conversion rate
        conversion_rate = metrics["prospect_metrics"]["outreach_conversion_rate"]
        if conversion_rate < thresholds.get("low_conversion_rate", 0.05):
            anomalies.append({
                "type": "low_conversion_rate",
                "message": f"Conversion rate is only {conversion_rate:.1%}, below the {thresholds.get('low_conversion_rate', 0.05):.1%} threshold.",
                "severity": "high"
            })

        # Check EPC
        epc = metrics["financial_metrics"]["epc"]
        if epc < thresholds.get("low_epc", 0.5):
            anomalies.append({
                "type": "low_epc",
                "message": f"Earnings per click (EPC) is only ${epc:.2f}, below the ${thresholds.get('low_epc', 0.5):.2f} threshold.",
                "severity": "medium"
            })

        # Check ROI
        roi = metrics["financial_metrics"]["roi"]
        if roi < thresholds.get("negative_roi", 0):
            anomalies.append({
                "type": "negative_roi",
                "message": f"ROI is negative at {roi:.1%}, indicating the program is not profitable.",
                "severity": "critical"
            })

        return anomalies

    async def analyze_performance(self, state: AffiliateSystemState) -> AffiliateSystemState:
        """
        Main method to analyze system performance and generate a report.

        Args:
            state: The current affiliate system state.

        Returns:
            The updated state with performance analysis and optimizations.
        """
        print("PerformanceAgent: Starting performance analysis...")

        # Calculate performance metrics
        metrics = await self._calculate_key_metrics(state)
        print("PerformanceAgent: Calculated key performance metrics.")

        # Generate optimization suggestions
        optimizations = await self._generate_optimizations(metrics)
        print(f"PerformanceAgent: Generated {len(optimizations)} optimization suggestions.")

        # Detect anomalies
        anomalies = await self._detect_anomalies(metrics)
        if anomalies:
            print(f"PerformanceAgent: Detected {len(anomalies)} performance anomalies.")

        # Compile complete performance report
        performance_report = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metrics": metrics,
            "optimizations": optimizations,
            "anomalies": anomalies,
            "summary": {
                "total_prospects": metrics["prospect_metrics"]["total_prospects"],
                "conversion_rate": metrics["prospect_metrics"]["outreach_conversion_rate"],
                "total_commissions": metrics["financial_metrics"]["total_commissions"],
                "epc": metrics["financial_metrics"]["epc"],
                "roi": metrics["financial_metrics"]["roi"]
            }
        }

        # Update state with performance report
        state.campaign_performance_report = performance_report

        # Update task description
        report_summary = (
            f"Performance Analysis: {metrics['prospect_metrics']['outreach_conversion_rate']:.1%} conversion rate, "
            f"${metrics['financial_metrics']['epc']:.2f} EPC, "
            f"{metrics['financial_metrics']['roi']:.1%} ROI."
        )
        current_desc = state.current_task_description if state.current_task_description is not None else ""
        state.current_task_description = f"{current_desc} {report_summary}"

        print(f"PerformanceAgent: Completed performance analysis. {report_summary}")

        # Set the next task based on analysis cycle completion
        state.current_task = "cycle_complete"

        return state
