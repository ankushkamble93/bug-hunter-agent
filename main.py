"""Runtime entry point for the localized bug hunter micro-agent."""

import asyncio

from bug_hunter.agent import BugHunterAgent


def main() -> None:
    agent = BugHunterAgent(project_root=".")
    asyncio.run(agent.run())


if __name__ == "__main__":
    main()
