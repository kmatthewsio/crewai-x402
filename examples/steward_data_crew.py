"""Example: CrewAI data crew paying Steward's x402 penny APIs.

This example shows a CrewAI crew buying real data from Steward
(pay.brianbooms.com) — USDC micropayments on Base via x402, no API keys.

Steward's machine-readable endpoint + price list:
    https://pay.brianbooms.com/.well-known/x402

To run:
    export WALLET_PRIVATE_KEY=0x...   # funded with USDC on Base
    export OPENAI_API_KEY=<redacted>
    python steward_data_crew.py
"""

import os

from crewai import Agent, Crew, Task

from crewai_x402 import X402Tool, X402Wallet

# Steward endpoints used in this example (all USDC on Base, eip155:8453)
STEWARD_WEATHER = "https://pay.brianbooms.com/api/v1/data/weather"   # $0.01
STEWARD_ISS_PASS = "https://pay.brianbooms.com/api/v1/data/iss-pass"  # $0.01
STEWARD_JOKE = "https://pay.brianbooms.com/api/v1/data/joke"          # $0.01


def create_steward_crew() -> Crew:
    """Create a crew that buys data from Steward's x402 API."""

    # Wallet with a $1 budget — plenty for penny data calls
    wallet = X402Wallet(
        private_key=os.environ["WALLET_PRIVATE_KEY"],
        network="eip155:8453",  # Base mainnet
        budget_usd=1.00,
    )
    payment_tool = X402Tool(wallet=wallet)

    researcher = Agent(
        role="Data Researcher",
        goal="Gather accurate, current data from paid x402 APIs",
        backstory=(
            "You buy data from Steward (pay.brianbooms.com), a pay-per-call "
            "x402 API on Base. Each call costs $0.01 USDC — no API keys, no "
            "signup. Never pay more than $0.05 for a single call."
        ),
        tools=[payment_tool],
        verbose=True,
    )

    writer = Agent(
        role="Brief Writer",
        goal="Turn raw data into a short readable brief",
        backstory="You write tight, factual briefs from the researcher's data.",
        verbose=True,
    )

    research_task = Task(
        description=(
            "1. Get the current weather in Austin, TX from "
            f"{STEWARD_WEATHER}?lat=30.27&lon=-97.74 (pay up to $0.01). "
            "2. Get upcoming visible ISS flyover times for the same location from "
            f"{STEWARD_ISS_PASS}?lat=30.27&lon=-97.74 (pay up to $0.01). "
            "3. Buy one joke from "
            f"{STEWARD_JOKE} (pay up to $0.01) for the brief's sign-off. "
            "Report the raw results with sources."
        ),
        expected_output="Weather summary, ISS pass times, and one joke, with URLs",
        agent=researcher,
    )

    writing_task = Task(
        description=(
            "Using the research findings, write a 5-line morning brief: "
            "weather, next ISS pass, and the joke as a sign-off."
        ),
        expected_output="Short morning brief, plain text",
        agent=writer,
    )

    return Crew(
        agents=[researcher, writer],
        tasks=[research_task, writing_task],
        verbose=True,
    )


if __name__ == "__main__":
    crew = create_steward_crew()
    result = crew.kickoff()
    print(result)
