"""Run the Cache maintainer gRPC server."""

import os
import sys
import traceback

from apme_engine.daemon.cache_maintainer_server import serve


def main() -> None:
    listen = os.environ.get("APME_CACHE_MAINTAINER_LISTEN", "0.0.0.0:50052")
    try:
        server = serve(listen)
        server.start()
        sys.stderr.write(f"Cache maintainer listening on {listen}\n")
        sys.stderr.flush()
        server.wait_for_termination()
    except Exception as e:
        sys.stderr.write(f"Cache maintainer failed: {e}\n")
        traceback.print_exc(file=sys.stderr)
        sys.stderr.flush()
        sys.exit(1)


if __name__ == "__main__":
    main()
