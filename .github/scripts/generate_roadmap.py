#!/usr/bin/env python3
"""
Generate roadmap.md from GitHub issues labeled 'roadmap'
"""
import os
import sys
from datetime import datetime
from typing import Any
import urllib.request
import json


def fetch_issues(repo: str, token: str, label: str = "roadmap") -> list[dict[str, Any]]:
    """Fetch all open issues with the specified label"""
    url = f"https://api.github.com/repos/{repo}/issues?labels={label}&state=all&per_page=100"
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "Authorization": f"token {token}",
    }

    req = urllib.request.Request(url, headers=headers)

    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode())
    except Exception as e:
        print(f"Error fetching issues: {e}", file=sys.stderr)
        return []


def group_issues_by_milestone(issues: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Group issues by milestone, with 'No Milestone' for issues without one"""
    grouped: dict[str, list[dict[str, Any]]] = {}

    for issue in issues:
        # Skip pull requests
        if "pull_request" in issue:
            continue

        milestone = issue.get("milestone")
        milestone_title = milestone["title"] if milestone else "No Milestone"

        if milestone_title not in grouped:
            grouped[milestone_title] = []

        grouped[milestone_title].append(issue)

    return grouped


def generate_task_checkbox(issue: dict[str, Any]) -> str:
    """Generate a checkbox item for an issue"""
    number = issue["number"]
    title = issue["title"]
    state = issue["state"]
    url = issue["html_url"]

    checkbox = "[x]" if state == "closed" else "[ ]"
    status_emoji = "✓" if state == "closed" else "🚧" if any(label["name"] == "in-progress" for label in issue.get("labels", [])) else ""

    return f"- {checkbox} **{title}** ([#{number}]({url})) {status_emoji}"


def generate_milestone_section(milestone: str, issues: list[dict[str, Any]]) -> str:
    """Generate markdown section for a milestone"""
    # Sort issues by number
    issues = sorted(issues, key=lambda x: x["number"])

    # Count completed tasks
    completed = sum(1 for issue in issues if issue["state"] == "closed")
    total = len(issues)

    # Generate section
    lines = [f"## {milestone}\n"]

    # Add milestone description if available (from first issue with this milestone)
    for issue in issues:
        milestone_obj = issue.get("milestone")
        if milestone_obj and milestone_obj.get("description"):
            lines.append(f"{milestone_obj['description']}\n")
            break

    lines.append("### Tasks\n")

    for issue in issues:
        lines.append(generate_task_checkbox(issue))

    lines.append(f"\n**Progress:** {completed}/{total} completed")

    # Add goal/benefits from issue body if available
    for issue in issues:
        body = issue.get("body", "")
        if body and len(issues) == 1:  # Only add body if single issue in milestone
            lines.append("\n### Details\n")
            lines.append(body[:500] + "..." if len(body) > 500 else body)

    lines.append("\n")

    return "\n".join(lines)


def generate_roadmap(issues: list[dict[str, Any]]) -> str:
    """Generate complete roadmap markdown"""
    grouped = group_issues_by_milestone(issues)

    lines = [
        "# Rapyer Roadmap\n",
        "This roadmap is automatically generated from GitHub issues labeled with `roadmap`.\n",
        f"Last updated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}\n",
        "[View all roadmap issues](https://github.com/imaginary-cherry/rapyer/issues?q=label%3Aroadmap) | "
        "[Create new roadmap issue](https://github.com/imaginary-cherry/rapyer/issues/new?labels=roadmap)\n",
    ]

    # Sort milestones: "No Milestone" last, others alphabetically
    milestones = sorted(grouped.keys(), key=lambda x: (x == "No Milestone", x))

    for milestone in milestones:
        lines.append(generate_milestone_section(milestone, grouped[milestone]))

    if not grouped:
        lines.append("\n*No roadmap items found. [Create your first roadmap issue!](https://github.com/imaginary-cherry/rapyer/issues/new?labels=roadmap)*\n")

    return "\n".join(lines)


def main():
    # Get environment variables
    repo = os.environ.get("GITHUB_REPOSITORY")
    token = os.environ.get("GITHUB_TOKEN")
    output_path = os.environ.get("OUTPUT_PATH", "docs/roadmap.md")

    if not repo or not token:
        print("Error: GITHUB_REPOSITORY and GITHUB_TOKEN must be set", file=sys.stderr)
        sys.exit(1)

    print(f"Fetching roadmap issues from {repo}...")
    issues = fetch_issues(repo, token)

    print(f"Found {len(issues)} issues")

    print("Generating roadmap...")
    roadmap_content = generate_roadmap(issues)

    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Write roadmap
    with open(output_path, "w") as f:
        f.write(roadmap_content)

    print(f"Roadmap generated at {output_path}")


if __name__ == "__main__":
    main()
