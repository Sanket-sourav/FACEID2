"""
CLI entrypoint for the attendance pipeline.

Usage:
    python main.py build-embeddings
    python main.py process-video --video data/videos/test.mp4
    python main.py process-video --video data/videos/test.mp4 --save-json
    python main.py serve                       # phone-friendly web UI -> Google Sheet
"""

import argparse
import os
from pathlib import Path

from src import config


def cmd_build_embeddings(args):
    from src.enrollment.build_embeddings import build

    build()


def cmd_process_video(args):
    from src.pipeline import print_report, process_video, save_report_json

    if not config.EMBEDDINGS_PATH.exists():
        raise SystemExit(
            f"No embeddings found at {config.EMBEDDINGS_PATH}.\n"
            f"Run 'python main.py build-embeddings' first (after enrolling students)."
        )

    decisions, stats = process_video(args.video)
    print_report(decisions, stats)

    if args.save_json:
        out_path = config.REPORTS_DIR / (Path(args.video).stem + "_report.json")
        save_report_json(decisions, stats, out_path)


def cmd_serve(args):
    import uvicorn

    # Railway / Heroku / most PaaS provide the listening port via $PORT.
    port = args.port or int(os.environ.get("PORT", "8000"))

    print(
        "\nAttendance web UI is ready.\n"
        "On the same Wi-Fi, open on your phone:\n"
        f"    http://<this-computer's-ip>:{port}\n"
        "If this is deployed to a public host (Railway etc.), use its public URL.\n"
        "Find your LAN IP with: python -c \"import socket; print(socket.gethostbyname(socket.gethostname()))\"\n"
    )
    uvicorn.run("app:app", host=args.host, port=port, reload=args.reload)


def main():
    parser = argparse.ArgumentParser(description="Classroom attendance recognition prototype")
    sub = parser.add_subparsers(dest="command", required=True)

    p_build = sub.add_parser("build-embeddings", help="Build embeddings.pkl from data/students/*")
    p_build.set_defaults(func=cmd_build_embeddings)

    p_proc = sub.add_parser("process-video", help="Run the full pipeline on a video and print an attendance report")
    p_proc.add_argument("--video", required=True, help="Path to classroom (or test) video")
    p_proc.add_argument("--save-json", action="store_true", help="Also save the report as JSON in data/reports/")
    p_proc.set_defaults(func=cmd_process_video)

    p_serve = sub.add_parser("serve", help="Run the phone-friendly web server (upload video -> Google Sheet)")
    p_serve.add_argument("--host", default="0.0.0.0", help="Interface to bind (default 0.0.0.0 = all)")
    p_serve.add_argument("--port", type=int, default=None, help="Port to listen on (default $PORT env var, else 8000)")
    p_serve.add_argument("--reload", action="store_true", help="Auto-reload on code changes (dev only)")
    p_serve.set_defaults(func=cmd_serve)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
