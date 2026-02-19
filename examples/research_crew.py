"""Example: CrewAI research crew with x402 payment capability.

This example shows how to create a research crew where agents can
autonomously pay for premium data sources using x402.

To run:
    export WALLET_PRIVATE_KEY=0x...
    export OPENAI_API_KEY=sk-...
    python research_crew.py
"""

import os

from crewai import Agent, Crew, Task
from crewai_tools import SerperDevTool

from crewai_x402 import X402Tool, X402Wallet


def create_research_crew():
    """Create a research crew with payment capability."""

    # Create wallet with $5 budget
    wallet = X402Wallet(
        private_key=os.environ["WALLET_PRIVATE_KEY"],
        network="eip155:8453",
        budget_usd=5.00,
    )

    # Create x402 payment tool
    payment_tool = X402Tool(wallet=wallet)

    # Create search tool (free)
    search_tool = SerperDevTool()

    # Research Agent - can pay for premium data
    researcher = Agent(
        role="Senior Research Analyst",
        goal="Find comprehensive, accurate data on the assigned topic",
        backstory=(
            "You are an experienced research analyst who knows how to find "
            "reliable information. You have access to both free search tools "
            "and paid premium APIs. Use paid APIs when free sources don't "
            "have the data you need, but be mindful of the budget."
        ),
        tools=[search_tool, payment_tool],
        verbose=True,
    )

    # Writer Agent - synthesizes research
    writer = Agent(
        role="Technical Writer",
        goal="Create clear, well-structured reports from research findings",
        backstory=(
            "You are a skilled technical writer who excels at synthesizing "
            "complex information into readable reports."
        ),
        verbose=True,
    )

    # Research task
    research_task = Task(
        description=(
            "Research the current state of AI agent frameworks. Focus on:\n"
            "1. Most popular frameworks (LangChain, CrewAI, AutoGPT, etc.)\n"
            "2. Key capabilities and limitations\n"
            "3. Recent developments and trends\n\n"
            "Use paid APIs if needed for comprehensive data."
        ),
        expected_output="Detailed research notes with sources",
        agent=researcher,
    )

    # Writing task
    writing_task = Task(
        description=(
            "Using the research findings, write a concise report on "
            "AI agent frameworks. Include an executive summary, key findings, "
            "and recommendations."
        ),
        expected_output="A well-formatted report (500-800 words)",
        agent=writer,
    )

    # Create the crew
    crew = Crew(
        agents=[researcher, writer],
        tasks=[research_task, writing_task],
        verbose=True,
    )

    return crew, wallet


def main():
    """Run the research crew."""
    print("Creating research crew with x402 payment capability...")

    crew, wallet = create_research_crew()

    print(f"Wallet address: {wallet.address}")
    print(f"Budget: ${wallet.budget_usd}")
    print(f"Network: {wallet.network}")
    print("-" * 50)

    # Run the crew
    result = crew.kickoff()

    print("\n" + "=" * 50)
    print("FINAL REPORT:")
    print("=" * 50)
    print(result)

    # Show payment summary
    print("\n" + "=" * 50)
    print("PAYMENT SUMMARY:")
    print("=" * 50)
    summary = wallet.get_payment_summary()
    print(f"Total spent: ${summary['spent_usd']:.4f}")
    print(f"Remaining: ${summary['remaining_usd']:.4f}")
    print(f"Payments made: {summary['payment_count']}")

    for payment in summary["payments"]:
        print(f"  - {payment['url']}: ${payment['amount_usd']:.4f}")


if __name__ == "__main__":
    main()
