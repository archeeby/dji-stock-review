"""Local, SHA-bound PR acceptance runner. No writes to personal DJI data.

Usage: python scripts/accept.py PR_NUMBER
A successful automated test run is NOT human UI approval.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


AI_PATHS = (
    "run_pipeline.py", "run_batch.py", "analyze_auto_single_frame_batch.py",
    "generate_stock_metadata_batch.py", "metadata_enrichment.py",
)
MEDIA_PATHS = (
    "export_approved.py", "detect_scenes_v4_batch.py",
    "analyze_camera_motion_batch.py", "analyze_composition_batch.py",
    "resolve_location.py", "export_stock_platforms.py", "stock/",
)
UI_PATHS = ("review_app.py", "candidate_reviews.py", "review_navigation.py", "trim_bounds.py")


def classify(paths):
    """Choose the most demanding relevant profile; unknown code fails toward media."""
    paths = list(paths)
    if not paths:
        raise ValueError("No PR changes found; cannot infer acceptance scope")
    if all(p.startswith("docs/") or p.endswith(".md") for p in paths):
        return "docs"
    if any(p in AI_PATHS or p.startswith("tests/test_ollama") for p in paths):
        return "ai"
    if any(p in MEDIA_PATHS or any(p.startswith(prefix) for prefix in ("stock/",))
           or p.startswith("tests/test_real_dji") for p in paths):
        return "media"
    if all(p in UI_PATHS or p.startswith("tests/") or p.startswith("scripts/")
           or p.startswith(".github/") or p.endswith(".md") for p in paths):
        return "unit"
    return "media"


def command(*args, cwd=None, capture=True, timeout=120):
    return subprocess.run(args, cwd=cwd, check=True, text=True,
                          capture_output=capture, timeout=timeout)


def prepare_worktree(repo, pr):
    command("git", "-C", str(repo), "fetch", "--no-tags", "origin", f"pull/{pr}/head")
    sha = command("git", "-C", str(repo), "rev-parse", "FETCH_HEAD").stdout.strip()
    command("git", "-C", str(repo), "fetch", "--no-tags", "origin", "main")
    changes = command("git", "-C", str(repo), "diff", "--name-only",
                      f"origin/main...{sha}").stdout.splitlines()
    target = Path.home() / ".dji-stock-previews" / f"pr-{pr}"
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if not (target / ".git").is_file():
            raise RuntimeError(f"Refusing to touch non-worktree directory: {target}")
        if command("git", "-C", str(target), "status", "--porcelain").stdout.strip():
            raise RuntimeError(f"PR worktree has local changes; refusing checkout: {target}")
        command("git", "-C", str(target), "checkout", "--detach", sha)
    else:
        command("git", "-C", str(repo), "worktree", "add", "--detach",
                str(target), sha)
    return sha, target, changes


def find_python(repo):
    for path in (repo / ".venv312/bin/python", repo / ".venv/bin/python"):
        if path.is_file():
            result = subprocess.run([str(path), "-c",
                "import sys, streamlit; assert sys.version_info[:2] == (3, 12)"],
                capture_output=True)
            if result.returncode == 0:
                return path
    raise RuntimeError("Missing Python 3.12 with Streamlit in .venv312 or .venv")


def prerequisites(profile, worktree):
    required = []
    if profile != "docs":
        # The default unittest discovery always executes real DJI media tests.
        required = ["ffmpeg", "ffprobe", "exiftool"]
        for test in ("tests/test_real_dji_tools.py", "tests/test_real_dji_motion.py"):
            if not (worktree / test).is_file():
                raise RuntimeError(f"Required real media integration test is not present: {test}")
    if profile == "ai":
        if not (worktree / "tests/test_ollama_e2e.py").is_file():
            raise RuntimeError("Required isolated Ollama E2E test is not implemented; merge blocked")
        required.append("ollama")
    missing = [name for name in required if shutil.which(name) is None]
    if missing:
        raise RuntimeError(f"Missing required tools: {', '.join(missing)}")


def execute(pr, repo):
    sha, worktree, changed = prepare_worktree(repo, pr)
    profile = classify(changed)
    report_dir = Path.home() / ".dji-stock-acceptance" / f"pr-{pr}" / sha
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "result.json"
    log_path = report_dir / "tests.log"
    report = {
        "schema_version": 2,
        "pr": pr, "head_sha": sha, "profile": profile, "changed_files": changed,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "environment": {"platform": sys.platform, "python": sys.version.split()[0]},
        "local_tests": "pending", "ui_acceptance": "pending",
        "log": str(log_path), "notes": [],
        "checks": [],
        "checks": {
            "unittest_discovery": {"status": "pending" if profile != "docs" else "not_applicable", "reason": "Documentation-only change" if profile == "docs" else None},
            "real_dji_opencv": {"status": "pending" if profile != "docs" else "not_applicable", "reason": "Included in unittest discovery" if profile != "docs" else "Documentation-only change"},
            "real_ffmpeg_exiftool": {"status": "pending" if profile != "docs" else "not_applicable", "reason": "Included in unittest discovery" if profile != "docs" else "Documentation-only change"},
            "ollama_e2e": {"status": "pending" if profile == "ai" else "not_applicable", "reason": None if profile == "ai" else "No AI/pipeline files changed"},
            "streamlit_preview": {"status": "pending" if profile != "docs" else "not_applicable", "reason": None if profile != "docs" else "Documentation-only change"},
        },
    }
    try:
        python = find_python(repo)
        report["environment"]["test_python"] = str(python)
        prerequisites(profile, worktree)
        if profile == "docs":
            report["checks"].append({"name": "automated_tests", "status": "not_applicable", "reason": "docs-only"})
            report["checks"].append({"name": "ollama_e2e", "status": "not_applicable", "reason": "docs-only"})
            report["local_tests"] = "not_applicable"
            report["ui_acceptance"] = "not_applicable"
            report["notes"].append("Documentation-only PR; GitHub Actions CI remains mandatory")
        else:
            args = [str(python), "-m", "unittest", "discover", "-s", "tests", "-v"]
            # Redirect Path.home() and temp writes away from ~/DroneStock during tests.
            # This is filesystem path isolation, not an OS-level security sandbox.
            with tempfile.TemporaryDirectory(prefix="dji-accept-home-") as sandbox:
                env = os.environ.copy()
                env["HOME"] = sandbox
                env["TMPDIR"] = sandbox
                with log_path.open("w", encoding="utf-8") as log:
                    result = subprocess.run(args, cwd=worktree, env=env, stdout=log,
                                            stderr=subprocess.STDOUT, timeout=1800)
                    report["checks"].append({"name": "unit_and_real_media", "status": "passed" if result.returncode == 0 else "failed", "exit_code": result.returncode})
                    if result.returncode:
                        raise RuntimeError(f"Local tests failed (exit {result.returncode}); see {log_path}")
                    if profile == "ai":
                        ai_env = env.copy()
                        ai_env["DJI_RUN_OLLAMA_E2E"] = "1"
                        result = subprocess.run(
                            [str(python), "-m", "unittest", "tests.test_ollama_e2e", "-v"],
                            cwd=worktree, env=ai_env, stdout=log, stderr=subprocess.STDOUT, timeout=3600,
                        )
                        report["checks"].append({"name": "ollama_e2e", "status": "passed" if result.returncode == 0 else "failed", "exit_code": result.returncode})
                        if result.returncode:
                            raise RuntimeError(f"Ollama E2E failed (exit {result.returncode}); see {log_path}")
                    else:
                        report["checks"].append({"name": "ollama_e2e", "status": "not_applicable", "reason": "no AI code changed"})
            report["local_tests"] = "passed"
            for name in ("unittest_discovery", "real_dji_opencv", "real_ffmpeg_exiftool"):
                report["checks"][name]["status"] = "passed"
            if profile == "ai":
                report["checks"]["ollama_e2e"]["status"] = "passed"
            report["notes"].append("UI acceptance is pending until the human verifies the preview")
    except Exception as exc:
        report["local_tests"] = "blocked"
        report["checks"]["failure"] = {"status": "blocked", "reason": str(exc)}
        report["error"] = str(exc)
        report_path.write_text(json.dumps(report, indent=2) + "\n")
        print(f"ACCEPTANCE BLOCKED: {exc}\nReport: {report_path}", file=sys.stderr)
        return 1
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    print(f"PR #{pr} SHA {sha}\nProfile: {profile}\nReport: {report_path}")
    if profile == "docs":
        print("Local UI acceptance N/A; confirm GitHub Actions and authorize merge separately.")
        return 0
    # Preview script re-fetches HEAD. Abort if the PR moved during testing.
    current = command("git", "-C", str(repo), "ls-remote", "origin",
                      f"refs/pull/{pr}/head").stdout.split()
    if not current or current[0] != sha:
        report["local_tests"] = "stale"
        report["checks"]["streamlit_preview"] = {"status": "blocked", "reason": "PR HEAD changed after tests"}
        report["error"] = "PR HEAD changed during local acceptance"
        report_path.write_text(json.dumps(report, indent=2) + "\n")
        print(report["error"], file=sys.stderr)
        return 1
    print("Tests passed. Launching Streamlit; UI acceptance remains manual.")
    print("WARNING: Streamlit preview SHARES ~/DroneStock runtime data. Avoid modifying real records.")
    preview_exit = subprocess.call(["bash", str(worktree / "scripts/preview.sh"), str(pr)], cwd=worktree)
    report["checks"]["streamlit_preview"] = {"status": "launched" if preview_exit == 0 else "blocked", "reason": "Human UI approval remains pending" if preview_exit == 0 else f"Preview exited with status {preview_exit}"}
    if preview_exit:
        report["error"] = f"Streamlit preview failed (exit {preview_exit})"
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    return preview_exit


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("pr", type=int)
    args = parser.parse_args()
    if args.pr <= 0:
        parser.error("PR number must be positive")
    repo = Path.home() / "DroneStock"
    if not (repo / ".git").exists():
        parser.error("Main checkout not found at ~/DroneStock")
    return execute(args.pr, repo)


if __name__ == "__main__":
    sys.exit(main())
