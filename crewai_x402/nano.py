"""
Feeless Nano (XNO) settlement helpers for CrewAI agents.

CrewAI x402 settles pay-per-call API charges in USDC via EIP-3009. USDC is
fast but the x402 facilitator carries a per-transaction cost and a minimum
that can make sub-cent per-call charges uneconomical to settle one by one.
Nano (XNO) is a feeless commit-chain with no merchant account and no
chargeback window, so its ``nano:`` payment URI is a clean way to settle a
sub-minimum remainder without a facilitator.

This module is dependency-free: it converts an integer micro-dollar amount to
an exact Nano ``raw`` amount and mints a standard ``nano:<account>?amount=<raw>``
payment URI. No float arithmetic is used, so no value is lost on sub-cent
inputs, and it never touches the x402 facilitator or the wallet.

Example::

    from crewai_x402.nano import micro_usd_to_raw, make_nano_pay_uri

    raw = micro_usd_to_raw(1500, 150_000_000)   # $0.0015 at $150/XNO
    uri = make_nano_pay_uri(
        "nano_1yo6c1t64ahfjdw1dxizmbbnpdmbrckwhw9phbg5pdkeubrizga4qhnjmnx7", raw
    )
    print(uri)  # nano:<account>?amount=10000000000000...
"""

from __future__ import annotations

import re

_ACCOUNT_RE = re.compile(r"^(nano|xrb)_[13][13-9a-km-uw-z]{59}$")

# Nano has 30 decimal places: 1 XNO = 10**30 raw.
_RAW_PER_XNO = 10**30
# raw-per-XNO is the only scale needed: raw = micro * 10**30 / price_micro_usd.


def micro_usd_to_raw(micro_dollars: int, xno_price_micro_usd: int) -> int:
    """
    Convert an integer micro-dollar amount to an exact Nano ``raw`` amount
    (ceil-rounded so value is never lost).

    Parameters
    ----------
    micro_dollars:
        The billed amount in integer micro-dollars (e.g. $0.0005 -> 500).
    xno_price_micro_usd:
        The XNO price in micro-dollars per whole XNO (e.g. 1 XNO =
        150_000_000 micro-dollars => $150).

    Returns
    -------
    int
        The raw amount to pay.

    Raises
    ------
    ValueError
        If ``micro_dollars`` is negative or ``xno_price_micro_usd`` is not
        positive.
    """
    if micro_dollars < 0 or xno_price_micro_usd <= 0:
        raise ValueError(
            "micro_dollars and xno_price_micro_usd must be non-negative "
            "(price > 0)"
        )
    if micro_dollars == 0:
        return 0
    numerator = micro_dollars * _RAW_PER_XNO
    raw, remainder = divmod(numerator, xno_price_micro_usd)
    if remainder:
        raw += 1
    return raw


def make_nano_pay_uri(
    account: str,
    raw: int,
    opts: dict[str, str] | None = None,
) -> str:
    """
    Mint a standard ``nano:<account>?amount=<raw>`` payment URI.

    Parameters
    ----------
    account:
        A valid Nano account (``nano_...`` or ``xrb_...``).
    raw:
        The raw amount to pay.
    opts:
        Optional ``{"label": ..., "message": ...}`` fields appended to the URI.

    Returns
    -------
    str
        The payment URI.

    Raises
    ------
    ValueError
        If ``account`` is not a valid Nano account.
    """
    if not _ACCOUNT_RE.match(account):
        raise ValueError(f"invalid Nano account: {account}")
    uri = f"nano:{account}?amount={int(raw)}"
    opts = opts or {}
    if opts.get("label"):
        uri += f"&label={_uri_quote(opts['label'])}"
    if opts.get("message"):
        uri += f"&message={_uri_quote(opts['message'])}"
    return uri


def _uri_quote(value: str) -> str:
    """Quote a URI query value without importing urllib.parse's heavy deps."""
    return re.sub(
        r"[^A-Za-z0-9\-._~]",
        lambda m: f"%{ord(m.group(0)):02X}",
        value,
    )
