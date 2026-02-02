"""X402 Payment Tool for CrewAI agents."""

import base64
import json
import time
from typing import Any, Type

import httpx
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from .wallet import X402Wallet


class X402ToolInput(BaseModel):
    """Input schema for X402Tool."""

    url: str = Field(..., description="The URL to request")
    method: str = Field(default="GET", description="HTTP method (GET, POST, etc.)")
    body: str | None = Field(default=None, description="Request body for POST/PUT")
    headers: dict[str, str] | None = Field(default=None, description="Additional headers")
    max_price_usd: float | None = Field(
        default=None,
        description="Maximum price willing to pay for this request in USD",
    )


class X402Tool(BaseTool):
    """CrewAI tool that enables agents to pay for API access using x402.

    This tool automatically handles 402 Payment Required responses by:
    1. Detecting the payment requirement
    2. Checking if the price is within budget
    3. Signing a USDC payment authorization
    4. Retrying the request with payment proof

    Example:
        wallet = X402Wallet(
            private_key=os.environ["WALLET_PRIVATE_KEY"],
            network="base-mainnet",
            budget_usd=10.00
        )
        tool = X402Tool(wallet=wallet)

        # Add to your crew
        agent = Agent(
            role="Research Assistant",
            tools=[tool],
            ...
        )
    """

    name: str = "x402_payment_request"
    description: str = (
        "Make HTTP requests to APIs that require x402 payment. "
        "Automatically handles payment negotiation using USDC. "
        "Use this when you need to access paid APIs or premium content. "
        "Input should include the URL and optionally method, body, headers, "
        "and max_price_usd to limit spending on a single request."
    )
    args_schema: Type[BaseModel] = X402ToolInput

    wallet: X402Wallet = Field(..., description="Wallet for making payments")
    auto_pay: bool = Field(
        default=True,
        description="Automatically pay when within budget",
    )
    timeout: float = Field(default=30.0, description="HTTP request timeout in seconds")

    # Headers from x402 spec
    _HEADER_PAYMENT_REQUIRED: str = "X-PAYMENT-REQUIRED"
    _HEADER_PAYMENT: str = "X-PAYMENT"
    _HEADER_PAYMENT_RESPONSE: str = "X-PAYMENT-RESPONSE"

    def _run(
        self,
        url: str,
        method: str = "GET",
        body: str | None = None,
        headers: dict[str, str] | None = None,
        max_price_usd: float | None = None,
    ) -> str:
        """Execute request with automatic x402 payment handling.

        Args:
            url: The URL to request
            method: HTTP method
            body: Request body for POST/PUT
            headers: Additional headers
            max_price_usd: Maximum price for this specific request

        Returns:
            Response content as string, or error message
        """
        request_headers = headers.copy() if headers else {}

        with httpx.Client(timeout=self.timeout) as client:
            # Initial request
            response = self._make_request(client, method, url, request_headers, body)

            # Check for 402 Payment Required
            if response.status_code == 402:
                return self._handle_payment_required(
                    client=client,
                    response=response,
                    method=method,
                    url=url,
                    headers=request_headers,
                    body=body,
                    max_price_usd=max_price_usd,
                )

            # Return response for other status codes
            if response.status_code >= 400:
                return f"Error {response.status_code}: {response.text}"

            return response.text

    def _make_request(
        self,
        client: httpx.Client,
        method: str,
        url: str,
        headers: dict[str, str],
        body: str | None,
    ) -> httpx.Response:
        """Make an HTTP request."""
        return client.request(
            method=method,
            url=url,
            headers=headers,
            content=body.encode() if body else None,
        )

    def _handle_payment_required(
        self,
        client: httpx.Client,
        response: httpx.Response,
        method: str,
        url: str,
        headers: dict[str, str],
        body: str | None,
        max_price_usd: float | None,
    ) -> str:
        """Handle a 402 Payment Required response."""
        # Get payment requirements from header
        payment_header = response.headers.get(self._HEADER_PAYMENT_REQUIRED)
        if not payment_header:
            return "Error: 402 response missing X-PAYMENT-REQUIRED header"

        try:
            requirements = json.loads(base64.b64decode(payment_header))
        except (json.JSONDecodeError, ValueError) as e:
            return f"Error: Failed to parse payment requirements: {e}"

        # Extract payment details
        accepts = requirements.get("accepts", [])
        if not accepts:
            return "Error: No payment options in requirements"

        # Find a compatible payment option
        payment_option = self._find_compatible_option(accepts)
        if not payment_option:
            return (
                f"Error: No compatible payment option. "
                f"Wallet network: {self.wallet.network}, "
                f"Available: {[a.get('network') for a in accepts]}"
            )

        # Check price
        max_amount = int(payment_option.get("maxAmountRequired", 0))
        price_usd = self.wallet.usdc_to_usd(max_amount)

        # Check against per-request limit
        if max_price_usd is not None and price_usd > max_price_usd:
            return (
                f"Error: Price ${price_usd:.4f} exceeds max_price_usd ${max_price_usd:.4f}"
            )

        # Check against wallet budget
        if not self.wallet.can_afford(price_usd):
            return (
                f"Error: Price ${price_usd:.4f} exceeds remaining budget "
                f"${self.wallet.remaining_usd:.4f}"
            )

        if not self.auto_pay:
            return (
                f"Payment required: ${price_usd:.4f} USDC to {payment_option.get('payTo')}. "
                f"Set auto_pay=True to pay automatically."
            )

        # Sign payment
        try:
            payment_data = self.wallet.sign_payment(
                to=payment_option["payTo"],
                amount_usd=price_usd,
                valid_before=int(time.time()) + 300,  # 5 minute validity
                resource_url=url,
            )
        except ValueError as e:
            return f"Error signing payment: {e}"

        # Build x402 payment payload
        payload = {
            "x402Version": 1,
            "scheme": "exact",
            "network": self.wallet.network,
            "payload": {
                "signature": payment_data["signature"],
                "authorization": {
                    "from": payment_data["from"],
                    "to": payment_data["to"],
                    "value": str(payment_data["value"]),
                    "validAfter": str(payment_data["validAfter"]),
                    "validBefore": str(payment_data["validBefore"]),
                    "nonce": payment_data["nonce"],
                },
            },
        }

        # Retry with payment
        headers[self._HEADER_PAYMENT] = base64.b64encode(
            json.dumps(payload).encode()
        ).decode()

        paid_response = self._make_request(client, method, url, headers, body)

        if paid_response.status_code >= 400:
            return (
                f"Error after payment: {paid_response.status_code} - "
                f"{paid_response.text}"
            )

        # Check for payment response header
        payment_response = paid_response.headers.get(self._HEADER_PAYMENT_RESPONSE)
        if payment_response:
            try:
                pr_data = json.loads(base64.b64decode(payment_response))
                tx_hash = pr_data.get("transactionHash", "unknown")
                return (
                    f"[Paid ${price_usd:.4f} USDC | tx: {tx_hash[:16]}...]\n\n"
                    f"{paid_response.text}"
                )
            except (json.JSONDecodeError, ValueError):
                pass

        return f"[Paid ${price_usd:.4f} USDC]\n\n{paid_response.text}"

    def _find_compatible_option(self, accepts: list[dict]) -> dict | None:
        """Find a payment option compatible with our wallet."""
        for option in accepts:
            if option.get("network") == self.wallet.network:
                return option
        return None

    def get_wallet_status(self) -> dict[str, Any]:
        """Get current wallet status and spending summary."""
        return self.wallet.get_payment_summary()
