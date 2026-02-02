"""CrewAI x402 integration - enable AI agents to pay for APIs with USDC."""

from .wallet import PaymentRecord, X402Wallet

__all__ = [
    "X402Wallet",
    "PaymentRecord",
]

# Import tool only if crewai is available
try:
    from .tool import X402Tool, X402ToolInput

    __all__.extend(["X402Tool", "X402ToolInput"])
except ImportError:
    # crewai not installed - tool not available
    pass

__version__ = "0.1.0"
