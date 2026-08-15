"""GaiaOS Conventional Commit Release Notes Generator.

Parses commit history between git tags (or up to target tag) and categorizes
conventional commit messages into markdown sections for GitHub Release bodies.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

_repo_root = Path(__file__).resolve().parent.parent

# Conventional commit regex patterns
CONVENTIONAL_REGEX = re.compile(
    r"^(?P<type>feat|fix|docs|refactor|perf|ci|build|ops|infra|chore|test)"
    r"(?:\((?P<scope>[^)]+)\))?"
    r"(?P<breaking>!)?: "
    r"(?P<subject>.+)$"
)


def get_commit_logs(tag: str | None = None, repo_dir: Path | None = None) -> list[str]:
    """Extract commit subjects and bodies since previous tag up to target tag/HEAD."""
    cwd = repo_dir or _repo_root

    # Determine previous tag if available
    prev_tag: str | None = None
    if tag:
        try:
            # Find closest tag prior to specified tag/ref
            tags_out = subprocess.check_output(
                ["git", "tag", "--sort=-creatordate"],
                cwd=cwd,
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip().splitlines()

            if tag in tags_out:
                idx = tags_out.index(tag)
                if idx + 1 < len(tags_out):
                    prev_tag = tags_out[idx + 1]
        except (subprocess.CalledProcessError, FileNotFoundError):
            prev_tag = None

    cmd = ["git", "log", "--pretty=format:%B---END_COMMIT---"]
    if prev_tag and tag:
        cmd.insert(2, f"{prev_tag}..{tag}")
    elif tag:
        cmd.insert(2, tag)

    try:
        raw_out = subprocess.check_output(cmd, cwd=cwd, text=True, stderr=subprocess.DEVNULL)
        return [c.strip() for c in raw_out.split("---END_COMMIT---") if c.strip()]
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []


def parse_and_categorize_commits(commits: list[str]) -> dict[str, list[str]]:
    """Categorize raw commit messages into structured release notes sections."""
    categories: dict[str, list[str]] = {
        "Breaking Changes": [],
        "New Features & Capabilities": [],
        "Bug Fixes & Corrections": [],
        "Documentation": [],
        "Performance & Refactoring": [],
        "Build, CI & Infrastructure": [],
        "Other Changes": [],
    }

    for commit in commits:
        lines = commit.splitlines()
        if not lines:
            continue

        header = lines[0].strip()

        # Check for explicit BREAKING CHANGE in body
        is_breaking = "BREAKING CHANGE:" in commit or "BREAKING-CHANGE:" in commit

        match = CONVENTIONAL_REGEX.match(header)
        if match:
            ctype = match.group("type")
            scope = match.group("scope")
            is_bang_breaking = bool(match.group("breaking"))
            subject = match.group("subject").strip()

            formatted_item = f"**{scope}**: {subject}" if scope else subject

            if is_breaking or is_bang_breaking:
                categories["Breaking Changes"].append(formatted_item)
            elif ctype == "feat":
                categories["New Features & Capabilities"].append(formatted_item)
            elif ctype == "fix":
                categories["Bug Fixes & Corrections"].append(formatted_item)
            elif ctype == "docs":
                categories["Documentation"].append(formatted_item)
            elif ctype in ("refactor", "perf"):
                categories["Performance & Refactoring"].append(formatted_item)
            elif ctype in ("ci", "build", "ops", "infra", "chore"):
                categories["Build, CI & Infrastructure"].append(formatted_item)
            else:
                categories["Other Changes"].append(formatted_item)
        else:
            if is_breaking:
                categories["Breaking Changes"].append(header)
            else:
                categories["Other Changes"].append(header)

    return categories


def generate_release_notes_markdown(
    tag: str | None = None, repo_dir: Path | None = None
) -> str:
    """Generate complete markdown release notes for a release tag."""
    commits = get_commit_logs(tag, repo_dir)
    categorized = parse_and_categorize_commits(commits)

    title = f"# GaiaOS Release Notes — {tag}\n" if tag else "# GaiaOS Release Notes\n"
    sections: list[str] = [title]

    for section_title, items in categorized.items():
        if items:
            sections.append(f"### {section_title}\n")
            for item in items:
                sections.append(f"- {item}")
            sections.append("")

    if len(sections) == 1:
        sections.append("No significant commit changes recorded for this release.\n")

    return "\n".join(sections)


def main() -> int:
    """CLI entrypoint for release notes generation."""
    parser = argparse.ArgumentParser(
        description="Generate markdown release notes from conventional commits."
    )
    parser.add_argument("--tag", help="Target release tag name (e.g. v1.0.0)")

    parser.add_argument("--output", type=Path, help="Output markdown file path")

    args = parser.parse_args()
    md_content = generate_release_notes_markdown(args.tag)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(md_content, encoding="utf-8")
        print(f"[OK] Release notes generated at {args.output}")
    else:
        print(md_content)

    return 0


if __name__ == "__main__":
    sys.exit(main())
