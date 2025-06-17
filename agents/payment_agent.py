import asyncio
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone
from ..core.state import AffiliateSystemState, Commission, CommissionStatus

class PaymentAgent:
    """
    Agent responsible for processing payments to affiliates.
    Handles payment methods, batching, and transaction logging.
    """
    def __init__(self,
                 composio_client: Any,  # Using Any for type flexibility
                 payment_config: Dict[str, Any]):
        """
        Initializes the PaymentAgent.

        Args:
            composio_client: Client for Composio tool integration.
            payment_config: Configuration for payments, e.g.,
                            {
                                "payment_methods": ["stripe_connect", "paypal", "crypto"],
                                "batch_payments": true,
                                "minimum_payment": 50.0,
                                "payment_schedule": "weekly",  # or "monthly", "daily"
                                "default_currency": "USD"
                            }
        """
        self.composio_client = composio_client
        self.payment_config = payment_config

    async def _get_affiliate_payment_preferences(self, affiliate_id: str) -> Dict[str, Any]:
        """
        Retrieves payment preferences for an affiliate.
        In a real implementation, this would query a database or CRM.
        """
        # Mock function to get affiliate payment preferences
        # In a real system, you'd fetch this from a database or CRM via Composio

        try:
            # Example: Query CRM for affiliate payment preferences
            params = {
                "affiliate_id": affiliate_id,
                "fields": ["payment_method", "payment_details"]
            }
            response = await self.composio_client.execute("CRM_GET_AFFILIATE", params)

            if response and response.get("status") == "success":
                data = response.get("data", {})
                return {
                    "payment_method": data.get("payment_method", "stripe_connect"),
                    "stripe_account_id": data.get("stripe_account_id"),
                    "paypal_email": data.get("paypal_email"),
                    "crypto_address": data.get("crypto_address"),
                    "crypto_currency": data.get("crypto_currency", "USDC")
                }
        except Exception as e:
            print(f"PaymentAgent: Error getting payment preferences for {affiliate_id}: {e}")

        # Fallback to default payment method
        return {
            "payment_method": self.payment_config.get("default_payment_method", "stripe_connect"),
            "stripe_account_id": f"mock_acct_{affiliate_id}",
            "paypal_email": f"{affiliate_id}@example.com",
            "crypto_address": None
        }

    async def _batch_commissions_by_affiliate(self,
                                             commissions: List[Commission]) -> Dict[str, List[Commission]]:
        """
        Groups commissions by affiliate ID for batch processing.
        """
        batched_commissions = {}

        for commission in commissions:
            if commission.affiliate_id not in batched_commissions:
                batched_commissions[commission.affiliate_id] = []
            batched_commissions[commission.affiliate_id].append(commission)

        return batched_commissions

    async def _process_stripe_payment(self,
                                     affiliate_id: str,
                                     commissions: List[Commission],
                                     payment_details: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Processes a Stripe Connect payment for an affiliate.
        """
        if not payment_details.get("stripe_account_id"):
            return False, "No Stripe account ID found for affiliate"

        total_amount = sum(c.commission_amount for c in commissions)
        commission_ids = [c.commission_id for c in commissions]

        try:
            params = {
                "amount": int(total_amount * 100),  # Convert to cents for Stripe
                "currency": self.payment_config.get("default_currency", "USD").lower(),
                "destination": payment_details["stripe_account_id"],
                "metadata": {
                    "affiliate_id": affiliate_id,
                    "commission_ids": ",".join(commission_ids),
                    "commission_count": len(commissions)
                }
            }

            response = await self.composio_client.execute("STRIPE_CREATE_TRANSFER", params)

            if response and response.get("status") == "success":
                return True, response.get("id", "unknown_transfer_id")
            else:
                return False, f"Stripe error: {response.get('error', 'Unknown error')}"

        except Exception as e:
            return False, f"Exception during Stripe payment: {e}"

    async def _process_paypal_payment(self,
                                     affiliate_id: str,
                                     commissions: List[Commission],
                                     payment_details: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Processes a PayPal payment for an affiliate.
        """
        if not payment_details.get("paypal_email"):
            return False, "No PayPal email found for affiliate"

        total_amount = sum(c.commission_amount for c in commissions)
        commission_ids = [c.commission_id for c in commissions]

        try:
            params = {
                "sender_batch_header": {
                    "email_subject": "Your affiliate commission payment",
                    "email_message": f"You have received a commission payment for {len(commissions)} sales."
                },
                "items": [
                    {
                        "recipient_type": "EMAIL",
                        "amount": {
                            "value": str(total_amount),
                            "currency": self.payment_config.get("default_currency", "USD")
                        },
                        "note": f"Commission payment for {len(commissions)} sales",
                        "sender_item_id": f"payment_{affiliate_id}_{datetime.now(timezone.utc).timestamp()}",
                        "receiver": payment_details["paypal_email"]
                    }
                ]
            }

            response = await self.composio_client.execute("PAYPAL_CREATE_PAYOUT", params)

            if response and response.get("status") == "success":
                return True, response.get("batch_header", {}).get("payout_batch_id", "unknown_batch_id")
            else:
                return False, f"PayPal error: {response.get('error', 'Unknown error')}"

        except Exception as e:
            return False, f"Exception during PayPal payment: {e}"

    async def _process_crypto_payment(self,
                                     affiliate_id: str,
                                     commissions: List[Commission],
                                     payment_details: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Processes a cryptocurrency payment for an affiliate.
        """
        if not payment_details.get("crypto_address"):
            return False, "No crypto address found for affiliate"

        total_amount = sum(c.commission_amount for c in commissions)
        commission_ids = [c.commission_id for c in commissions]
        crypto_currency = payment_details.get("crypto_currency", "USDC")

        try:
            # Convert amount to crypto if needed
            # For stablecoins like USDC, the conversion is typically 1:1
            crypto_amount = total_amount

            params = {
                "address": payment_details["crypto_address"],
                "amount": str(crypto_amount),
                "currency": crypto_currency,
                "note": f"Commission payment for {affiliate_id}"
            }

            response = await self.composio_client.execute("CRYPTO_SEND_PAYMENT", params)

            if response and response.get("status") == "success":
                return True, response.get("transaction_id", "unknown_tx_id")
            else:
                return False, f"Crypto payment error: {response.get('error', 'Unknown error')}"

        except Exception as e:
            return False, f"Exception during crypto payment: {e}"

    async def process_payments(self, state: AffiliateSystemState) -> AffiliateSystemState:
        """
        Main method to process payments for approved commissions.

        Args:
            state: The current affiliate system state.

        Returns:
            The updated affiliate system state with payment results.
        """
        print("PaymentAgent: Starting payment processing...")

        # Get commissions eligible for payment (status = APPROVED)
        eligible_commissions = [c for c in state.commissions_log
                              if c.status == CommissionStatus.APPROVED]

        if not eligible_commissions:
            print("PaymentAgent: No approved commissions found for payment.")
            current_desc = state.current_task_description if state.current_task_description is not None else ""
            state.current_task_description = f"{current_desc} No commissions to pay."
            return state

        print(f"PaymentAgent: Found {len(eligible_commissions)} commissions eligible for payment.")

        # Check if we should batch payments
        batch_payments = self.payment_config.get("batch_payments", True)

        if batch_payments:
            # Process payments in batches by affiliate
            batched_commissions = await self._batch_commissions_by_affiliate(eligible_commissions)
            print(f"PaymentAgent: Batched commissions for {len(batched_commissions)} affiliates.")

            successful_payments = 0
            failed_payments = 0
            total_amount_paid = 0.0

            for affiliate_id, commissions in batched_commissions.items():
                # Get affiliate payment preferences
                payment_preferences = await self._get_affiliate_payment_preferences(affiliate_id)
                payment_method = payment_preferences.get("payment_method", "stripe_connect")

                # Calculate total amount for this affiliate
                batch_amount = sum(c.commission_amount for c in commissions)
                minimum_payment = self.payment_config.get("minimum_payment", 50.0)

                if batch_amount < minimum_payment:
                    print(f"PaymentAgent: Batch amount ${batch_amount:.2f} for {affiliate_id} below minimum payment threshold ${minimum_payment:.2f}. Skipping.")
                    continue

                # Process payment based on payment method
                success = False
                transaction_id = ""

                if payment_method == "stripe_connect":
                    success, transaction_id = await self._process_stripe_payment(
                        affiliate_id, commissions, payment_preferences)
                elif payment_method == "paypal":
                    success, transaction_id = await self._process_paypal_payment(
                        affiliate_id, commissions, payment_preferences)
                elif payment_method == "crypto":
                    success, transaction_id = await self._process_crypto_payment(
                        affiliate_id, commissions, payment_preferences)
                else:
                    print(f"PaymentAgent: Unsupported payment method {payment_method} for {affiliate_id}")
                    failed_payments += 1
                    continue

                # Update commission statuses based on payment result
                if success:
                    print(f"PaymentAgent: Successfully paid ${batch_amount:.2f} to {affiliate_id} via {payment_method}. Transaction ID: {transaction_id}")
                    successful_payments += 1
                    total_amount_paid += batch_amount

                    # Update commission statuses in state
                    for commission in commissions:
                        commission.status = CommissionStatus.PAID
                else:
                    print(f"PaymentAgent: Failed to pay {affiliate_id}. Reason: {transaction_id}")
                    failed_payments += 1
        else:
            # Process each commission individually
            successful_payments = 0
            failed_payments = 0
            total_amount_paid = 0.0

            for commission in eligible_commissions:
                # Get affiliate payment preferences
                payment_preferences = await self._get_affiliate_payment_preferences(commission.affiliate_id)
                payment_method = payment_preferences.get("payment_method", "stripe_connect")

                # Check if commission meets minimum payment threshold
                minimum_payment = self.payment_config.get("minimum_payment", 50.0)
                if commission.commission_amount < minimum_payment:
                    print(f"PaymentAgent: Commission amount ${commission.commission_amount:.2f} below minimum threshold. Skipping.")
                    continue

                # Process individual payment
                success = False
                transaction_id = ""

                if payment_method == "stripe_connect":
                    success, transaction_id = await self._process_stripe_payment(
                        commission.affiliate_id, [commission], payment_preferences)
                elif payment_method == "paypal":
                    success, transaction_id = await self._process_paypal_payment(
                        commission.affiliate_id, [commission], payment_preferences)
                elif payment_method == "crypto":
                    success, transaction_id = await self._process_crypto_payment(
                        commission.affiliate_id, [commission], payment_preferences)
                else:
                    print(f"PaymentAgent: Unsupported payment method {payment_method}")
                    failed_payments += 1
                    continue

                # Update commission status based on payment result
                if success:
                    print(f"PaymentAgent: Successfully paid ${commission.commission_amount:.2f} to {commission.affiliate_id}. Transaction ID: {transaction_id}")
                    successful_payments += 1
                    total_amount_paid += commission.commission_amount
                    commission.status = CommissionStatus.PAID
                else:
                    print(f"PaymentAgent: Failed to pay commission {commission.commission_id}. Reason: {transaction_id}")
                    failed_payments += 1

        # Update state with payment summary
        payment_summary = f"Payments: {successful_payments} successful (${total_amount_paid:.2f}), {failed_payments} failed."
        current_desc = state.current_task_description if state.current_task_description is not None else ""
        state.current_task_description = f"{current_desc} {payment_summary}"

        print(f"PaymentAgent: Completed payment processing. {payment_summary}")

        return state
