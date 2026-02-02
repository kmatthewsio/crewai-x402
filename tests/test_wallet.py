"""Tests for X402Wallet."""

import pytest

from crewai_x402 import X402Wallet


# Test private key (DO NOT use in production)
TEST_PRIVATE_KEY = "0x" + "a" * 64


class TestX402Wallet:
    """Tests for wallet initialization and properties."""

    def test_wallet_creation_with_key(self):
        """Wallet should initialize with provided private key."""
        wallet = X402Wallet(
            private_key=TEST_PRIVATE_KEY,
            network="base-sepolia",
            budget_usd=5.0,
        )
        assert wallet.address.startswith("0x")
        assert len(wallet.address) == 42
        assert wallet.network == "base-sepolia"
        assert wallet.budget_usd == 5.0

    def test_wallet_creation_generates_key(self):
        """Wallet should generate a new key if none provided."""
        wallet = X402Wallet(network="base-mainnet", budget_usd=10.0)
        assert wallet.address.startswith("0x")
        assert len(wallet.address) == 42

    def test_wallet_invalid_network(self):
        """Wallet should reject unknown networks."""
        with pytest.raises(ValueError, match="Unknown network"):
            X402Wallet(
                private_key=TEST_PRIVATE_KEY,
                network="invalid-network",
            )

    def test_wallet_chain_id(self):
        """Wallet should return correct chain ID for network."""
        wallet = X402Wallet(private_key=TEST_PRIVATE_KEY, network="base-mainnet")
        assert wallet.chain_id == 8453

        wallet = X402Wallet(private_key=TEST_PRIVATE_KEY, network="base-sepolia")
        assert wallet.chain_id == 84532

    def test_wallet_usdc_address(self):
        """Wallet should return correct USDC address for network."""
        wallet = X402Wallet(private_key=TEST_PRIVATE_KEY, network="base-mainnet")
        assert wallet.usdc_address == "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"


class TestWalletBudget:
    """Tests for budget management."""

    def test_initial_budget(self):
        """Wallet should track initial budget."""
        wallet = X402Wallet(
            private_key=TEST_PRIVATE_KEY,
            network="base-sepolia",
            budget_usd=10.0,
        )
        assert wallet.budget_usd == 10.0
        assert wallet.spent_usd == 0.0
        assert wallet.remaining_usd == 10.0

    def test_can_afford(self):
        """can_afford should check against remaining budget."""
        wallet = X402Wallet(
            private_key=TEST_PRIVATE_KEY,
            network="base-sepolia",
            budget_usd=1.0,
        )
        assert wallet.can_afford(0.50)
        assert wallet.can_afford(1.0)
        assert not wallet.can_afford(1.01)

    def test_reset_budget(self):
        """reset_budget should clear spending and optionally update budget."""
        wallet = X402Wallet(
            private_key=TEST_PRIVATE_KEY,
            network="base-sepolia",
            budget_usd=10.0,
        )
        # Simulate spending
        wallet._spent_usd = 5.0

        wallet.reset_budget()
        assert wallet.spent_usd == 0.0
        assert wallet.budget_usd == 10.0

        wallet.reset_budget(new_budget=20.0)
        assert wallet.budget_usd == 20.0


class TestWalletConversions:
    """Tests for USD/USDC conversions."""

    def test_usd_to_usdc(self):
        """Should convert USD to USDC smallest units (6 decimals)."""
        wallet = X402Wallet(private_key=TEST_PRIVATE_KEY, network="base-sepolia")
        assert wallet.usd_to_usdc(1.0) == 1_000_000
        assert wallet.usd_to_usdc(0.01) == 10_000
        assert wallet.usd_to_usdc(0.000001) == 1

    def test_usdc_to_usd(self):
        """Should convert USDC smallest units to USD."""
        wallet = X402Wallet(private_key=TEST_PRIVATE_KEY, network="base-sepolia")
        assert wallet.usdc_to_usd(1_000_000) == 1.0
        assert wallet.usdc_to_usd(10_000) == 0.01
        assert wallet.usdc_to_usd(1) == 0.000001


class TestWalletSigning:
    """Tests for payment signing."""

    def test_sign_payment(self):
        """sign_payment should return valid signature data."""
        wallet = X402Wallet(
            private_key=TEST_PRIVATE_KEY,
            network="base-sepolia",
            budget_usd=10.0,
        )

        result = wallet.sign_payment(
            to="0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb2",
            amount_usd=0.01,
            valid_before=9999999999,
            resource_url="https://api.example.com/data",
        )

        assert "signature" in result
        assert result["signature"].startswith("0x")
        assert "nonce" in result
        assert result["from"] == wallet.address
        assert result["to"] == "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb2"
        assert result["value"] == 10_000  # $0.01 in USDC units

    def test_sign_payment_updates_spent(self):
        """sign_payment should update spent amount."""
        wallet = X402Wallet(
            private_key=TEST_PRIVATE_KEY,
            network="base-sepolia",
            budget_usd=10.0,
        )

        wallet.sign_payment(
            to="0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb2",
            amount_usd=0.01,
            valid_before=9999999999,
        )

        assert wallet.spent_usd == 0.01
        assert wallet.remaining_usd == 9.99

    def test_sign_payment_records_payment(self):
        """sign_payment should record payment in history."""
        wallet = X402Wallet(
            private_key=TEST_PRIVATE_KEY,
            network="base-sepolia",
            budget_usd=10.0,
        )

        wallet.sign_payment(
            to="0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb2",
            amount_usd=0.01,
            valid_before=9999999999,
            resource_url="https://api.example.com/data",
        )

        assert len(wallet.payments) == 1
        assert wallet.payments[0].amount_usd == 0.01
        assert wallet.payments[0].resource_url == "https://api.example.com/data"

    def test_sign_payment_exceeds_budget(self):
        """sign_payment should raise if amount exceeds budget."""
        wallet = X402Wallet(
            private_key=TEST_PRIVATE_KEY,
            network="base-sepolia",
            budget_usd=1.0,
        )

        with pytest.raises(ValueError, match="Cannot afford"):
            wallet.sign_payment(
                to="0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb2",
                amount_usd=1.01,
                valid_before=9999999999,
            )


class TestPaymentSummary:
    """Tests for payment summary."""

    def test_get_payment_summary(self):
        """get_payment_summary should return correct structure."""
        wallet = X402Wallet(
            private_key=TEST_PRIVATE_KEY,
            network="base-sepolia",
            budget_usd=10.0,
        )

        wallet.sign_payment(
            to="0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb2",
            amount_usd=0.01,
            valid_before=9999999999,
            resource_url="https://api.example.com/data",
        )

        summary = wallet.get_payment_summary()

        assert summary["wallet_address"] == wallet.address
        assert summary["network"] == "base-sepolia"
        assert summary["budget_usd"] == 10.0
        assert summary["spent_usd"] == 0.01
        assert summary["remaining_usd"] == 9.99
        assert summary["payment_count"] == 1
        assert len(summary["payments"]) == 1
