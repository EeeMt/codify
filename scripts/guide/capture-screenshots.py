#!/usr/bin/env python3
"""Capture the in-app guide's UI screenshots from a running Codify instance.

Screenshots are generated, never hand-taken: a stale screenshot in a guide is
worse than no screenshot, so the only supported workflow is to re-run this
script after a UI change.

Usage:

    # First run: complete the login once; the session is stored for later runs.
    python3 scripts/guide/capture-screenshots.py --login

    # Subsequent runs reuse the stored session.
    python3 scripts/guide/capture-screenshots.py

    # Capture a task/issue detail page as well.
    python3 scripts/guide/capture-screenshots.py --task-id 670 --issue-id 183

The stored session is a real credential: it lives in `.cache/`, which is
git-ignored.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from playwright.sync_api import BrowserContext, Page, sync_playwright

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = REPO_ROOT / "frontend" / "src" / "guide" / "assets" / "screenshots"
DEFAULT_STATE = REPO_ROOT / ".cache" / "guide-auth.json"
DEFAULT_BASE_URL = "http://192.168.50.129:8880"

# Pages that need no record ids. The slug is the file name written to --out.
PAGES: list[tuple[str, str]] = [
    ("dashboard", "/dashboard"),
    ("issue-list", "/issues"),
    ("issue-create", "/issues/create"),
    ("task-list", "/tasks"),
    ("sessions", "/sessions"),
    ("schedule-overview", "/schedule-overview"),
    ("analytics", "/analytics"),
    ("monitor", "/monitor"),
    ("configuration", "/configuration"),
    ("access-management", "/access-management"),
    ("usage-management", "/usage-management"),
    ("system-statistics", "/system-statistics"),
]

# Charts animate and the app polls; freezing motion keeps captures repeatable.
FREEZE_CSS = """
*, *::before, *::after {
  animation: none !important;
  transition: none !important;
  caret-color: transparent !important;
}
"""

APP_SHELL_SELECTOR = ".app-shell, .n-layout"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help=f"running instance (default: {DEFAULT_BASE_URL})")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="output directory for PNGs")
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE, help="stored browser session path")
    parser.add_argument("--locale", choices=["en", "zh-CN"], default="en", help="app locale to capture in")
    parser.add_argument("--width", type=int, default=1600)
    parser.add_argument("--height", type=int, default=1000)
    parser.add_argument("--login", action="store_true", help="open a headed browser and wait for interactive login")
    parser.add_argument("--headed", action="store_true", help="run headed even when a session already exists")
    parser.add_argument("--task-id", type=int, help="also capture /tasks/<id>")
    parser.add_argument("--issue-id", type=int, help="also capture /issues/<id>")
    parser.add_argument("--only", nargs="*", help="capture only these slugs")
    return parser.parse_args()


def is_authenticated(page: Page, base_url: str) -> bool:
    try:
        response = page.request.get(f"{base_url}/api/auth/me", timeout=10_000)
        return bool(response.json().get("authenticated"))
    except Exception:
        return False


def wait_for_login(page: Page, base_url: str, timeout_seconds: int = 600) -> bool:
    print("Waiting for login. Complete the OIDC sign-in in the opened browser window...")
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if is_authenticated(page, base_url):
            print("Authenticated.")
            return True
        page.wait_for_timeout(2_000)
    return False


def capture(page: Page, slug: str, path: str, out_dir: Path, width: int) -> Path:
    page.goto(path, wait_until="domcontentloaded")
    page.wait_for_selector(APP_SHELL_SELECTOR, timeout=30_000)
    try:
        page.wait_for_load_state("networkidle", timeout=15_000)
    except Exception:
        # Polling pages never go idle; the rendered shell is what matters.
        pass
    page.add_style_tag(content=FREEZE_CSS)
    page.wait_for_timeout(400)

    target = out_dir / f"{slug}.png"
    page.screenshot(path=str(target), full_page=True)
    # A visual regression guard: a blank page would produce a tiny PNG.
    if target.stat().st_size < 8_000:
        print(f"  WARNING {slug}: only {target.stat().st_size} bytes, the page may not have rendered", file=sys.stderr)
    return target


def main() -> int:
    args = parse_args()
    base_url = args.base_url.rstrip("/")

    if not args.state.exists() and not args.login:
        print(
            f"No stored session at {args.state}.\n"
            "Run once with --login to authenticate interactively; later runs reuse the session.",
            file=sys.stderr,
        )
        return 2

    args.out.mkdir(parents=True, exist_ok=True)
    args.state.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not (args.login or args.headed))
        context: BrowserContext = browser.new_context(
            viewport={"width": args.width, "height": args.height},
            device_scale_factor=2,
            locale="zh-CN" if args.locale == "zh-CN" else "en-US",
            timezone_id="Asia/Shanghai",
            color_scheme="light",
            storage_state=str(args.state) if args.state.exists() else None,
        )
        context.add_init_script(f"localStorage.setItem('codify-locale', {json.dumps(args.locale)});")
        page = context.new_page()

        page.goto(base_url, wait_until="domcontentloaded")
        if not is_authenticated(page, base_url):
            if not args.login:
                print(
                    "The stored session is no longer valid. Re-run with --login.",
                    file=sys.stderr,
                )
                browser.close()
                return 2
            if not wait_for_login(page, base_url):
                print("Login timed out.", file=sys.stderr)
                browser.close()
                return 2
            context.storage_state(path=str(args.state))
            print(f"Session stored at {args.state} (git-ignored).")

        wanted = set(args.only) if args.only else None
        targets = [(slug, path) for slug, path in PAGES if not wanted or slug in wanted]
        if args.task_id:
            targets.append(("task-detail", f"/tasks/{args.task_id}"))
        if args.issue_id:
            targets.append(("issue-detail", f"/issues/{args.issue_id}"))

        failures: list[str] = []
        for slug, path in targets:
            try:
                written = capture(page, slug, path, args.out, args.width)
                print(f"  {written.relative_to(REPO_ROOT)} ({written.stat().st_size // 1024} KB)")
            except Exception as error:
                failures.append(f"{slug} ({path}): {error}")
                print(f"  FAILED {slug} ({path}): {error}", file=sys.stderr)

        browser.close()

    print(f"\n{len(targets) - len(failures)}/{len(targets)} screenshots written to {args.out.relative_to(REPO_ROOT)}")
    if failures:
        print("Failures:", file=sys.stderr)
        for failure in failures:
            print(f"  {failure}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
