"""Run with uv run --project web/sync python -m harmonic_sync."""
from __future__ import annotations

import argparse
import json


def main() -> None:
    parser = argparse.ArgumentParser(description="Harmonic analyzer kinematic video sync")
    commands = parser.add_subparsers(dest="command", required=True)
    census = commands.add_parser("shots", help="Preserve human shot census and probe the current source video")
    census.add_argument("video_id")
    for name, help_text in (("keyframes", "Extract keyframes and a prompt-authoring contact sheet"),
                            ("source", "Propagate SAM2 machine masks, edges and static source motion")):
        command = commands.add_parser(name, help=help_text)
        command.add_argument("video_id")
        command.add_argument("--shot")
    review = commands.add_parser("review", help="Regenerate the mask-overlay review sheet")
    review.add_argument("video_id")
    args = parser.parse_args()
    if args.command == "shots":
        from .census import extract_shots
        result = extract_shots(args.video_id)
        print(json.dumps({"videoId": result["videoId"], "sourceSha256": result["sourceSha256"],
                          "fps": result["fps"], "shots": len(result["shots"])}))
    elif args.command == "keyframes":
        from .source import keyframes
        print(keyframes(args.video_id, args.shot))
    elif args.command == "source":
        from .source import source
        result = source(args.video_id, args.shot)
        print(json.dumps({"videoId": args.video_id, "seconds": result["seconds"], "views": len(result["views"])}))
    elif args.command == "review":
        from .source import make_review
        print(make_review(args.video_id))


if __name__ == "__main__":
    main()
