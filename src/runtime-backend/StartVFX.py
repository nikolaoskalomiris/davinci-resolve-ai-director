from __future__ import annotations

import argparse

from VFXRuntime import VFXRuntime, VFXRuntimeError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Start the AI Director DaVinci Resolve runtime.")
    parser.add_argument("request", nargs="*", help="Natural-language DaVinci Resolve / VFX request.")
    parser.add_argument("--list-tools", action="store_true")
    args = parser.parse_args(argv)

    runtime = VFXRuntime()
    try:
        if args.list_tools:
            for name in sorted(runtime.discover_tools()):
                print(name)
            return 0
        request = " ".join(args.request).strip() or input("AI Director > ").strip()
        if not request:
            print("[AI Director ERROR] Request is empty.")
            return 2
        result = runtime.run_turn(request)
        for call in result.tool_calls:
            print(f"[TOOL] {call.tool_name} — completed")
        print(f"\nAI Director > {result.final_message}")
        return 0
    except VFXRuntimeError as exc:
        print(f"[AI Director ERROR] {exc}")
        return 1
    except KeyboardInterrupt:
        print("\n[AI Director] Session terminated by user.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
