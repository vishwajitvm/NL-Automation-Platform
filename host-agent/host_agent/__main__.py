import argparse
import asyncio
import logging
import sys

from .client import HostAgentClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [host-agent] %(message)s"
)


def main():
    parser = argparse.ArgumentParser(description="NL-Automation Host Agent")
    parser.add_argument("command", choices=["run"], help="Command to execute")
    parser.add_argument("--token", required=True, help="Host agent token generated from web dashboard or API")
    parser.add_argument("--server", default="http://localhost:8080", help="API gateway base URL")
    parser.add_argument("--interval", type=int, default=30, help="Metrics reporting interval in seconds")

    args = parser.parse_args()

    client = HostAgentClient(
        token=args.token,
        server_url=args.server,
        report_interval=args.interval
    )

    try:
        asyncio.run(client.run_loop())
    except KeyboardInterrupt:
        print("\nHost agent stopped by user.")
        sys.exit(0)


if __name__ == "__main__":
    main()
