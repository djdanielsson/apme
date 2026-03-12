"""Run the Primary daemon gRPC server."""

import asyncio
import os
import sys
import traceback

from apme_engine.daemon.primary_server import serve


async def _run(listen: str) -> None:
    server = await serve(listen)
    sys.stderr.write(f"Primary daemon listening on {listen}\n")
    sys.stderr.flush()
    await server.wait_for_termination()


def main() -> None:
    listen = os.environ.get("APME_PRIMARY_LISTEN", "0.0.0.0:50051")
    try:
        asyncio.run(_run(listen))
    except Exception as e:
        sys.stderr.write(f"Primary daemon failed: {e}\n")
        traceback.print_exc(file=sys.stderr)
        sys.stderr.flush()
        sys.exit(1)


if __name__ == "__main__":
    main()
