#!/usr/bin/env python3
import json
import os
import urllib.request
from datetime import datetime


GITHUB_API = "https://api.github.com"


def make_request(url, token=None):
    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"token {token}"

    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req) as response:
        return json.loads(response.read().decode())


def fetch_milestones(owner, repo, token):
    url = f"{GITHUB_API}/repos/{owner}/{repo}/milestones?state=all&per_page=100"
    return make_request(url, token)


def fetch_issues_for_milestone(owner, repo, milestone_number, token):
    url = f"{GITHUB_API}/repos/{owner}/{repo}/issues?milestone={milestone_number}&state=all&per_page=100"
    return make_request(url, token)


def generate_roadmap_markdown(milestones_data):
    lines = [
        "# Roadmap",
        "",
        "This roadmap is automatically generated from [GitHub Issues](https://github.com/{repo}/issues).",
        "",
        f"*Last updated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}*",
        "",
    ]

    for milestone in milestones_data:
        milestone_title = milestone["title"]
        issues = milestone["issues"]

        if not issues:
            continue

        closed_count = sum(1 for issue in issues if issue["state"] == "closed")
        total_count = len(issues)
        progress = f"{closed_count}/{total_count} completed"

        lines.append(f"## {milestone_title}")
        lines.append("")
        lines.append(f"*{progress}*")
        lines.append("")

        for issue in sorted(
            issues, key=lambda x: (x["state"] == "closed", x["number"])
        ):
            checkbox = "[x]" if issue["state"] == "closed" else "[ ]"
            title = issue["title"]
            url = issue["html_url"]
            number = issue["number"]
            lines.append(f"- {checkbox} [{title}]({url}) (#{number})")

        lines.append("")

    return "\n".join(lines)


def main():
    token = os.environ.get("GITHUB_TOKEN")
    repository = os.environ.get("GITHUB_REPOSITORY", "imaginary-cherry/rapyer")
    output_path = os.environ.get("OUTPUT_PATH", "docs/roadmap.md")

    owner, repo = repository.split("/")

    milestones = fetch_milestones(owner, repo, token)

    milestones_data = []
    for milestone in sorted(milestones, key=lambda m: m.get("due_on") or "9999"):
        issues = fetch_issues_for_milestone(owner, repo, milestone["number"], token)
        issues = [i for i in issues if "pull_request" not in i]

        milestones_data.append(
            {
                "title": milestone["title"],
                "description": milestone.get("description", ""),
                "state": milestone["state"],
                "issues": issues,
            }
        )

    markdown = generate_roadmap_markdown(milestones_data)
    markdown = markdown.replace("{repo}", repository)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        f.write(markdown)

    print(f"Generated roadmap at {output_path}")
    print(f"Found {len(milestones_data)} milestones with issues")


if __name__ == "__main__":
    main()
