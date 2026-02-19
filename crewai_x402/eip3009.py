"""EIP-3009 signature utilities for x402 payments."""

from typing import Any

from eth_account import Account


# Network configurations (CAIP-2 keys, with legacy aliases)
NETWORKS: dict[str, dict[str, Any]] = {
    # CAIP-2 format (canonical)
    "eip155:8453": {
        "chain_id": 8453,
        "usdc_address": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
        "name": "USD Coin",
        "version": "2",
    },
    "eip155:84532": {
        "chain_id": 84532,
        "usdc_address": "0x036CbD53842c5426634e7929541eC2318f3dCF7e",
        "name": "USD Coin",
        "version": "2",
    },
    "eip155:1": {
        "chain_id": 1,
        "usdc_address": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
        "name": "USD Coin",
        "version": "2",
    },
    "eip155:11155111": {
        "chain_id": 11155111,
        "usdc_address": "0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238",
        "name": "USD Coin",
        "version": "2",
    },
    "eip155:5042002": {
        "chain_id": 5042002,
        "usdc_address": "0x3600000000000000000000000000000000000000",
        "name": "USD Coin",
        "version": "2",
    },
    # Legacy aliases (backwards compat)
    "base-mainnet": {
        "chain_id": 8453,
        "usdc_address": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
        "name": "USD Coin",
        "version": "2",
    },
    "base-sepolia": {
        "chain_id": 84532,
        "usdc_address": "0x036CbD53842c5426634e7929541eC2318f3dCF7e",
        "name": "USD Coin",
        "version": "2",
    },
    "ethereum-mainnet": {
        "chain_id": 1,
        "usdc_address": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
        "name": "USD Coin",
        "version": "2",
    },
    "ethereum-sepolia": {
        "chain_id": 11155111,
        "usdc_address": "0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238",
        "name": "USD Coin",
        "version": "2",
    },
    "arc-testnet": {
        "chain_id": 5042002,
        "usdc_address": "0x3600000000000000000000000000000000000000",
        "name": "USD Coin",
        "version": "2",
    },
}


def build_transfer_authorization_typed_data(
    network: str,
    from_address: str,
    to_address: str,
    value: int,
    valid_after: int,
    valid_before: int,
    nonce: bytes,
) -> dict[str, Any]:
    """Build EIP-712 typed data for TransferWithAuthorization."""
    config = NETWORKS.get(network)
    if not config:
        raise ValueError(f"Unknown network: {network}")

    return {
        "types": {
            "EIP712Domain": [
                {"name": "name", "type": "string"},
                {"name": "version", "type": "string"},
                {"name": "chainId", "type": "uint256"},
                {"name": "verifyingContract", "type": "address"},
            ],
            "TransferWithAuthorization": [
                {"name": "from", "type": "address"},
                {"name": "to", "type": "address"},
                {"name": "value", "type": "uint256"},
                {"name": "validAfter", "type": "uint256"},
                {"name": "validBefore", "type": "uint256"},
                {"name": "nonce", "type": "bytes32"},
            ],
        },
        "primaryType": "TransferWithAuthorization",
        "domain": {
            "name": config["name"],
            "version": config["version"],
            "chainId": config["chain_id"],
            "verifyingContract": config["usdc_address"],
        },
        "message": {
            "from": from_address,
            "to": to_address,
            "value": value,
            "validAfter": valid_after,
            "validBefore": valid_before,
            "nonce": nonce if isinstance(nonce, bytes) else bytes.fromhex(nonce.replace("0x", "")),
        },
    }


def sign_transfer_authorization(
    private_key: str,
    network: str,
    from_address: str,
    to_address: str,
    value: int,
    valid_after: int,
    valid_before: int,
    nonce: bytes,
) -> str:
    """Sign a TransferWithAuthorization message and return the signature."""
    typed_data = build_transfer_authorization_typed_data(
        network=network,
        from_address=from_address,
        to_address=to_address,
        value=value,
        valid_after=valid_after,
        valid_before=valid_before,
        nonce=nonce,
    )

    # Sign the message - pass types without EIP712Domain (library adds it)
    message_types = {
        k: v for k, v in typed_data["types"].items() if k != "EIP712Domain"
    }

    account = Account.from_key(private_key)
    signed = account.sign_typed_data(
        typed_data["domain"],
        message_types,
        typed_data["message"],
    )

    return "0x" + signed.signature.hex()
