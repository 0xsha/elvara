from __future__ import annotations

import argparse
import json
from pathlib import Path

import uvicorn

from .server import create_app
from .service import IntentService, RunIntentOptions


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Elvara offchain PoC tools")
    subparsers = parser.add_subparsers(dest="command", required=True)

    serve = subparsers.add_parser("serve", help="Run the FastAPI intent server")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)

    generate = subparsers.add_parser("generate-intent", help="Generate and optionally publish an intent")
    generate.add_argument("--strategy", default="CVaR")
    generate.add_argument("--epoch", type=int)
    generate.add_argument("--expiry-seconds", type=int)
    generate.add_argument("--submit-onchain", action="store_true")
    generate.add_argument("--sample", action="store_true")
    generate.add_argument(
        "--today",
        action="store_true",
        help="Use today's date as the optimizer end date for live runs.",
    )
    generate.add_argument("--weights-mode", choices=("last", "avg"), default="last")
    generate.add_argument("--output")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "serve":
        uvicorn.run(create_app(), host=args.host, port=args.port, reload=False)
        return

    service = IntentService()
    try:
        result = service.run_rebalance(
            RunIntentOptions(
                strategy=args.strategy,
                epoch=args.epoch,
                expiry_seconds=args.expiry_seconds,
                submit_onchain=args.submit_onchain,
                use_sample=args.sample,
                use_today=args.today,
                weights_mode=args.weights_mode,
            )
        )
    except (RuntimeError, ValueError) as exc:
        parser.exit(status=2, message=f"error: {exc}\n")

    output = json.dumps(result, indent=2, sort_keys=True)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_output = json.dumps(result["artifact"], indent=2, sort_keys=True)
        output_path.write_text(f"{artifact_output}\n", encoding="utf-8")
    else:
        print(output)


if __name__ == "__main__":
    main()
