"""Tests for X402Tool."""

import base64
import json

import pytest

from crewai_x402 import X402Tool, X402Wallet


# Test private key (DO NOT use in production)
TEST_PRIVATE_KEY = "0x" + "a" * 64


@pytest.fixture
def wallet():
    """Create a test wallet."""
    return X402Wallet(
        private_key=TEST_PRIVATE_KEY,
        network="base-sepolia",
        budget_usd=10.0,
    )


@pytest.fixture
def tool(wallet):
    """Create a test tool."""
    return X402Tool(wallet=wallet)


class TestX402ToolInit:
    """Tests for tool initialization."""

    def test_tool_creation(self, wallet):
        """Tool should initialize with wallet."""
        tool = X402Tool(wallet=wallet)
        assert tool.wallet == wallet
        assert tool.auto_pay is True
        assert tool.timeout == 30.0

    def test_tool_with_options(self, wallet):
        """Tool should accept configuration options."""
        tool = X402Tool(
            wallet=wallet,
            auto_pay=False,
            timeout=60.0,
        )
        assert tool.auto_pay is False
        assert tool.timeout == 60.0

    def test_tool_has_correct_name(self, tool):
        """Tool should have correct name for CrewAI."""
        assert tool.name == "x402_payment_request"

    def test_tool_has_description(self, tool):
        """Tool should have a description."""
        assert len(tool.description) > 0
        assert "x402" in tool.description.lower()


class TestFindCompatibleOption:
    """Tests for payment option matching."""

    def test_find_compatible_option_match(self, tool):
        """Should find matching network option."""
        accepts = [
            {"network": "base-mainnet", "maxAmountRequired": "10000"},
            {"network": "base-sepolia", "maxAmountRequired": "10000"},
        ]
        result = tool._find_compatible_option(accepts)
        assert result is not None
        assert result["network"] == "base-sepolia"

    def test_find_compatible_option_no_match(self, tool):
        """Should return None when no compatible network."""
        accepts = [
            {"network": "ethereum-mainnet", "maxAmountRequired": "10000"},
        ]
        result = tool._find_compatible_option(accepts)
        assert result is None


class TestWalletStatus:
    """Tests for wallet status retrieval."""

    def test_get_wallet_status(self, tool, wallet):
        """get_wallet_status should return wallet summary."""
        status = tool.get_wallet_status()
        assert status["wallet_address"] == wallet.address
        assert status["network"] == "base-sepolia"
        assert status["budget_usd"] == 10.0
        assert status["spent_usd"] == 0.0


class TestToolInputSchema:
    """Tests for input schema validation."""

    def test_input_schema_exists(self, tool):
        """Tool should have args_schema defined."""
        assert tool.args_schema is not None

    def test_input_schema_fields(self, tool):
        """Input schema should have expected fields."""
        schema = tool.args_schema.model_json_schema()
        properties = schema.get("properties", {})
        assert "url" in properties
        assert "method" in properties
        assert "body" in properties
        assert "headers" in properties
        assert "max_price_usd" in properties
