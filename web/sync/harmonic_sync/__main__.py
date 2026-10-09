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
    # Fitting/reporting is deliberately separate from the source stages.
    fit = commands.add_parser("fit", help="Fit native cameras, setup and crank; validate every source sample")
    fit.add_argument("video_id")
    fit.add_argument("--shot", help="Private development fit only; do not replace the runtime track")
    fit.add_argument("--width", type=int, default=480)
    fit.add_argument("--force", action="store_true", help="Ignore valid per-shot checkpoints")
    fit.add_argument("--url", help="Attach to an existing headless render harness URL")
    report = commands.add_parser("report", help="Regenerate the private validation summary without rendering")
    report.add_argument("video_id")
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
    elif args.command == "fit":
        from .fit.pipeline import fit_video
        print(json.dumps(fit_video(args.video_id, shot_id=args.shot, width=args.width, force=args.force, url=args.url), allow_nan=False))
    elif args.command == "report":
        from .fit.report import write_report
        from .video import data_root
        print(json.dumps(write_report(args.video_id, data_root()), allow_nan=False))


if __name__ == "__main__":
    main()
