"""Entry point script for running the robot in polling mode."""

import asyncio

from far.main import main

if __name__ == "__main__":
    asyncio.run(main())
