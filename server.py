"""YookAI HTTP server entry point."""

import argparse

from tools.configure import interactive_config

from core.config import ensure_config, load_config
from core.log import setup_logger
from core.paths import ensure_layout
from app.server import YookAIServer

VERSION = "0.3.28"

def build_parser():
    parser = argparse.ArgumentParser(description="YookAI standalone multi-model AI client")
    parser.add_argument("--port", type=int, default=None, help="Server port")
    parser.add_argument("--host", default=None, help="Server host")
    parser.add_argument("--no-open", action="store_true", help="Do not open a browser")
    parser.add_argument("--no-configure", action="store_true", help="Skip the interactive pre-listen configuration menu")
    parser.add_argument("--configure", action="store_true", help="Force the interactive pre-listen configuration menu")
    return parser

def main(argv=None):
    args = build_parser().parse_args(argv)
    logger = setup_logger("yookai")
    ensure_layout()
    settings_path = ensure_config()
    config = load_config()
    if not args.no_configure:
        configured = interactive_config(config, force=args.configure)
        if configured is None:
            print("YookAI startup cancelled.")
            return 0
        config = configured
    host = args.host if args.host is not None else config["server"]["host"]
    port = args.port if args.port is not None else config["server"]["port"]
    print(f"YookAI v{VERSION}")
    logger.info("Configuration: %s", settings_path)
    display_host = f"[{host}]" if ":" in str(host) and not str(host).startswith("[") else host
    print(f"URL: http://{display_host}:{port}/")
    if args.no_open:
        logger.info("Browser auto-open disabled")
    server = YookAIServer(host, port, config)
    try:
        server.run()
    except KeyboardInterrupt:
        logger.info("Stopping YookAI")
        server.stop()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
