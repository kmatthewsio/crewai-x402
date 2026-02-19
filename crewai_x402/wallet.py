"""X402 Wallet for managing agent payment capabilities."""

import os
import secrets
from dataclasses import dataclass, field
from datetime import datetime

from eth_account import Account

from .eip3009 import NETWORKS, sign_transfer_authorization


@dataclass
class PaymentRecord:
    """Record of a payment made by the wallet."""

    resource_url: str
    amount_usd: float
    amount_usdc: int
    recipient: str
    signature: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    nonce: str = ""
    valid_before: int = 0


class X402Wallet:
    """Wallet for x402 payments with budget management.

    Manages a private key and tracks spending against a USD budget.
    Signs EIP-3009 TransferWithAuthorization messages for x402 payments.
    """

    USDC_DECIMALS = 6

    def __init__(
        self,
        private_key: str | None = None,
        network: str = "eip155:8453",
        budget_usd: float = 10.0,
    ):
        """Initialize wallet.

        Args:
            private_key: Hex-encoded private key. If None, generates a new one.
            network: Network name (e.g., "base-mainnet", "base-sepolia")
            budget_usd: Maximum USD amount this wallet can spend
        """
        if private_key is None:
            private_key = "0x" + secrets.token_hex(32)

        self._private_key = private_key
        self._account = Account.from_key(private_key)
        self._network = network
        self._budget_usd = budget_usd
        self._spent_usd = 0.0
        self._payments: list[PaymentRecord] = []

        if network not in NETWORKS:
            raise ValueError(
                f"Unknown network: {network}. "
                f"Supported: {', '.join(NETWORKS.keys())}"
            )

    @property
    def address(self) -> str:
        """Get the wallet address."""
        return self._account.address

    @property
    def network(self) -> str:
        """Get the network name."""
        return self._network

    @property
    def chain_id(self) -> int:
        """Get the chain ID for the network."""
        return NETWORKS[self._network]["chain_id"]

    @property
    def usdc_address(self) -> str:
        """Get the USDC contract address for the network."""
        return NETWORKS[self._network]["usdc_address"]

    @property
    def budget_usd(self) -> float:
        """Get the total budget in USD."""
        return self._budget_usd

    @property
    def spent_usd(self) -> float:
        """Get the total spent in USD."""
        return self._spent_usd

    @property
    def remaining_usd(self) -> float:
        """Get the remaining budget in USD."""
        return self._budget_usd - self._spent_usd

    @property
    def payments(self) -> list[PaymentRecord]:
        """Get the list of payment records."""
        return self._payments.copy()

    def can_afford(self, amount_usd: float) -> bool:
        """Check if the wallet can afford a payment."""
        return amount_usd <= self.remaining_usd

    def usd_to_usdc(self, usd: float) -> int:
        """Convert USD to USDC smallest units (6 decimals)."""
        return int(usd * (10**self.USDC_DECIMALS))

    def usdc_to_usd(self, usdc: int) -> float:
        """Convert USDC smallest units to USD."""
        return usdc / (10**self.USDC_DECIMALS)

    def sign_payment(
        self,
        to: str,
        amount_usd: float,
        valid_before: int,
        valid_after: int = 0,
        resource_url: str = "",
    ) -> dict:
        """Sign a payment authorization.

        Args:
            to: Recipient address
            amount_usd: Amount in USD
            valid_before: Unix timestamp when authorization expires
            valid_after: Unix timestamp when authorization becomes valid (default 0)
            resource_url: URL of resource being paid for (for tracking)

        Returns:
            dict with signature, nonce, and payment details

        Raises:
            ValueError: If amount exceeds remaining budget
        """
        if not self.can_afford(amount_usd):
            raise ValueError(
                f"Cannot afford ${amount_usd:.4f}. "
                f"Remaining budget: ${self.remaining_usd:.4f}"
            )

        amount_usdc = self.usd_to_usdc(amount_usd)
        nonce = secrets.token_bytes(32)

        signature = sign_transfer_authorization(
            private_key=self._private_key,
            network=self._network,
            from_address=self.address,
            to_address=to,
            value=amount_usdc,
            valid_after=valid_after,
            valid_before=valid_before,
            nonce=nonce,
        )

        # Record the payment
        self._spent_usd += amount_usd
        payment = PaymentRecord(
            resource_url=resource_url,
            amount_usd=amount_usd,
            amount_usdc=amount_usdc,
            recipient=to,
            signature=signature,
            nonce=nonce.hex(),
            valid_before=valid_before,
        )
        self._payments.append(payment)

        return {
            "signature": signature,
            "nonce": nonce.hex(),
            "from": self.address,
            "to": to,
            "value": amount_usdc,
            "validAfter": valid_after,
            "validBefore": valid_before,
        }

    def get_payment_summary(self) -> dict:
        """Get a summary of all payments made."""
        return {
            "wallet_address": self.address,
            "network": self._network,
            "budget_usd": self._budget_usd,
            "spent_usd": self._spent_usd,
            "remaining_usd": self.remaining_usd,
            "payment_count": len(self._payments),
            "payments": [
                {
                    "url": p.resource_url,
                    "amount_usd": p.amount_usd,
                    "recipient": p.recipient,
                    "timestamp": p.timestamp.isoformat(),
                }
                for p in self._payments
            ],
        }

    def reset_budget(self, new_budget: float | None = None) -> None:
        """Reset the budget and clear payment history.

        Args:
            new_budget: New budget in USD. If None, keeps current budget.
        """
        if new_budget is not None:
            self._budget_usd = new_budget
        self._spent_usd = 0.0
        self._payments.clear()

    @classmethod
    def from_env(
        cls,
        key_env_var: str = "WALLET_PRIVATE_KEY",
        network: str = "eip155:8453",
        budget_usd: float = 10.0,
    ) -> "X402Wallet":
        """Create a wallet from an environment variable.

        Args:
            key_env_var: Name of environment variable containing private key
            network: Network name
            budget_usd: Maximum USD budget

        Returns:
            X402Wallet instance
        """
        private_key = os.environ.get(key_env_var)
        if not private_key:
            raise ValueError(f"Environment variable {key_env_var} not set")
        return cls(private_key=private_key, network=network, budget_usd=budget_usd)
