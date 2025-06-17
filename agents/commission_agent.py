import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone, timedelta
from ..core.state import AffiliateLead, AffiliateSystemState, Commission, CommissionStatus, LeadStatus

class CommissionAgent:
    """
    Agent responsible for real-time commission tracking and attribution.
    Tracks sales, calculates commissions, and prepares payment data.
    """
    def __init__(self,
                 composio_client: Any,  # Using Any for type flexibility
                 commission_config: Dict[str, Any]):
        """
        Initializes the CommissionAgent.

        Args:
            composio_client: Client for Composio tool integration.
            commission_config: Configuration for commission tracking, e.g.,
                             {
                                "default_commission_rate": 0.7,
                                "recurring_commission_rate": 0.05,
                                "performance_tiers": {
                                    "tier1": {"threshold": 10, "bonus": 0.05},
                                    "tier2": {"threshold": 25, "bonus": 0.10},
                                    "tier3": {"threshold": 50, "bonus": 0.15}
                                },
                                "payment_threshold": 50.0,  # Minimum amount for payment
                                "attribution_model": {
                                    "firstClick": 0.3,
                                    "lastClick": 0.4,
                                    "linear": 0.3
                                }
                             }
        """
        self.composio_client = composio_client
        self.commission_config = commission_config

    async def _fetch_sales_data(self) -> List[Dict[str, Any]]:
        """
        Fetches sales data from payment processors using Composio tools.
        Returns mock sales data.
        """
        print("CommissionAgent: Fetching mock sales data...")
        await asyncio.sleep(0.1) # Simulate async operation

        # Mock sales data. Affiliate IDs should match potential leads from SocialScoutAgent
        # e.g., "yt_ai_channel_1", "tw_saas_guru_1"
        mock_sales = [
            {
                "source": "mock_stripe",
                "transaction_id": "mock_stripe_tx_001",
                "amount": 100.00,
                "affiliate_id": "yt_ai_channel_1", # Assuming this lead will be converted
                "created_at": datetime.now(timezone.utc) - timedelta(hours=10),
                "metadata": {"product_id": "prod_A", "customer_id": "cust_123"}
            },
            {
                "source": "mock_paypal",
                "transaction_id": "mock_paypal_tx_002",
                "amount": 75.50,
                "affiliate_id": "tw_saas_guru_1", # Assuming this lead will be converted
                "created_at": datetime.now(timezone.utc) - timedelta(hours=5),
                "metadata": {"product_id": "prod_B", "customer_id": "cust_456"}
            },
            {
                "source": "mock_stripe",
                "transaction_id": "mock_stripe_tx_003",
                "amount": 25.00,
                "affiliate_id": "yt_ai_channel_1", # Another sale for this affiliate
                "created_at": datetime.now(timezone.utc) - timedelta(hours=2),
                "metadata": {"product_id": "prod_C", "customer_id": "cust_789"}
            },
            {
                "source": "mock_stripe",
                "transaction_id": "mock_stripe_tx_004",
                "amount": 50.00,
                "affiliate_id": "unknown_affiliate_id", # This affiliate might not exist
                "created_at": datetime.now(timezone.utc) - timedelta(hours=1),
                "metadata": {"product_id": "prod_D", "customer_id": "cust_000"}
            }
        ]
        print(f"CommissionAgent: Found {len(mock_sales)} mock sales transactions.")
        return mock_sales

    def _extract_affiliate_id(self, transaction_data: Dict[str, Any]) -> Optional[str]:
        """
        Extracts affiliate ID from transaction data.
        This could be in metadata, custom fields, or URL parameters.
        """
        # Different payment processors store affiliate data differently
        # This is a simplified example

        # Check metadata first
        metadata = transaction_data.get("metadata", {})
        if metadata.get("affiliate_id"):
            return metadata.get("affiliate_id")

        # Check URL referrer or tracking parameters
        if transaction_data.get("referrer_url"):
            # Extract from URL parameters like ?ref=affiliate_id
            url = transaction_data.get("referrer_url")
            if "?ref=" in url:
                return url.split("?ref=")[1].split("&")[0]

        # Check custom fields specific to the payment processor
        if transaction_data.get("custom_fields"):
            custom_fields = transaction_data.get("custom_fields")
            if custom_fields.get("affiliate_id"):
                return custom_fields.get("affiliate_id")

        return None

    def _calculate_commission(self, sale: Dict[str, Any], affiliate_id: str) -> Commission:
        """
        Calculate commission based on sale amount and affiliate settings.
        Applies performance tiers and bonuses if applicable.
        """
        # Get base commission rate from config or affiliate-specific settings
        base_rate = self.commission_config.get("default_commission_rate", 0.7)

        # Apply performance tier bonus if applicable
        # In a real implementation, you'd look up the affiliate's performance tier
        bonus_rate = 0.0
        monthly_sale_count = 15  # Mock value, would be retrieved from state or database

        # Apply performance tier bonuses based on monthly sales
        tiers = self.commission_config.get("performance_tiers", {})
        for tier, data in tiers.items():
            if monthly_sale_count >= data.get("threshold", 0):
                bonus_rate = data.get("bonus", 0.0)

        # Calculate final commission
        total_rate = base_rate + bonus_rate
        commission_amount = sale["amount"] * total_rate

        # Create Commission object
        commission = Commission(
            commission_id=f"comm_{sale['transaction_id']}",
            affiliate_id=affiliate_id,
            sale_amount=sale["amount"],
            commission_rate=total_rate,
            commission_amount=commission_amount,
            sale_date=sale["created_at"].isoformat(),
            status=CommissionStatus.PENDING,
            product_id=sale.get("product_id"),
            customer_id=sale.get("customer_id")
        )

        return commission

    async def _process_payment(self, commission: Commission) -> bool:
        """
        Process payment for a commission if it meets the threshold.
        """
        payment_threshold = self.commission_config.get("payment_threshold", 50.0)

        if commission.commission_amount < payment_threshold:
            print(f"CommissionAgent: Commission {commission.commission_id} below payment threshold.")
            return False

        try:
            # Get affiliate payment details
            # In a real implementation, you'd look up the affiliate's payment method
            payment_method = "stripe_connect"  # Mock value
            payment_details = {"account_id": f"acct_{commission.affiliate_id}"}

            # Process payment via Composio (Mocked)
            print(f"CommissionAgent: Simulating payment processing for commission {commission.commission_id} via {payment_method}...")
            await asyncio.sleep(0.1) # Simulate async operation

            # Simulate success for this mock
            # In a real scenario, you might want to simulate failures too based on some logic
            is_payment_successful = True

            if is_payment_successful:
                print(f"CommissionAgent: Mock payment successful for commission {commission.commission_id}.")
                commission.status = CommissionStatus.PAID
                return True
            else:
                print(f"CommissionAgent: Mock payment failed for commission {commission.commission_id}.")
                # Optionally set commission status to FAILED or PENDING_RETRY
                return False

        except Exception as e:
            print(f"CommissionAgent: Error during mock payment processing for commission {commission.commission_id}: {e}")
            return False

    async def track_commissions(self, state: AffiliateSystemState) -> AffiliateSystemState:
        """
        Main method to track commissions from sales data and process payments.

        Args:
            state: The current affiliate system state.

        Returns:
            The updated affiliate system state with new commissions.
        """
        print("CommissionAgent: Starting commission tracking...")

        # Fetch sales data from payment processors
        sales_data = await self._fetch_sales_data()
        print(f"CommissionAgent: Found {len(sales_data)} new sales transactions.")

        if not sales_data:
            current_desc = state.current_task_description if state.current_task_description is not None else ""
            state.current_task_description = f"{current_desc} No new sales found for commission tracking."
            return state

        # Calculate commissions for each sale
        new_commissions = []
        for sale in sales_data:
            affiliate_id = sale.get("affiliate_id")
            if not affiliate_id:
                continue

            # Check if this affiliate exists in our system
            affiliate_exists = any(
                aff.lead_id == affiliate_id
                for aff in state.active_affiliates
            )

            if not affiliate_exists:
                # Check if it's in prospects with CONVERTED status
                # Note: CRMAgent should have moved CONVERTED prospects to active_affiliates
                # This check here is a fallback or for a state where CRMAgent hasn't run post-conversion.
                prospect = next(
                    (p for p in state.prospects if p.lead_id == affiliate_id and p.status == LeadStatus.CONVERTED),
                    None
                )
                if not prospect:
                    print(f"CommissionAgent: Affiliate ID {affiliate_id} not found in system. Skipping commission.")
                    continue

            # Calculate commission
            commission = self._calculate_commission(sale, affiliate_id)
            new_commissions.append(commission)

            # Process payment if commission meets threshold
            if commission.commission_amount >= self.commission_config.get("payment_threshold", 50.0):
                payment_success = await self._process_payment(commission)
                if payment_success:
                    commission.status = CommissionStatus.PAID
                    print(f"CommissionAgent: Payment processed for commission {commission.commission_id}")
                else:
                    print(f"CommissionAgent: Payment processing failed for commission {commission.commission_id}")

        # Update state with new commissions
        state.commissions_log.extend(new_commissions)

        # Update state description
        current_desc = state.current_task_description if state.current_task_description is not None else ""
        state.current_task_description = f"{current_desc} Processed {len(new_commissions)} new commissions."
        print(f"CommissionAgent: Added {len(new_commissions)} new commissions to state.")

        return state
