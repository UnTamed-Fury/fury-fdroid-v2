"""
Fetch releases from GitHub API.

Fetches all releases for a given GitHub repository,
filtering out drafts and applying prerelease rules.
"""

import os
from typing import Any, Optional

import requests


def fetch_releases(
    github_repo: str,
    ignore_drafts: bool = True,
    prefer_prerelease: bool = False,
    include_prerelease_if_no_stable: bool = True,
) -> list[dict[str, Any]]:
    """
    Fetch releases from GitHub API.

    Args:
        github_repo: Repository in format "owner/repo"
        ignore_drafts: Whether to ignore draft releases
        prefer_prerelease: Whether to prefer prereleases over stable
        include_prerelease_if_no_stable: Include prereleases if no stable found

    Returns:
        List of release dictionaries
    """
    api_url = f"https://api.github.com/repos/{github_repo}/releases"

    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "Fury-FDroid-Repo/1.0",
    }

    # Add GitHub token if available (for rate limiting)
    github_token = os.environ.get("GITHUB_TOKEN")
    if github_token:
        headers["Authorization"] = f"Bearer {github_token}"

    try:
        response = requests.get(api_url, headers=headers, timeout=30)
        response.raise_for_status()
        releases = response.json()
    except requests.RequestException as e:
        raise RuntimeError(f"Failed to fetch releases: {e}") from e

    if not isinstance(releases, list):
        raise RuntimeError("Invalid response from GitHub API")

    # Filter out drafts if required
    if ignore_drafts:
        releases = [r for r in releases if not r.get("draft", False)]

    # Filter releases with no assets
    releases = [r for r in releases if r.get("assets", [])]

    # Apply prerelease filtering
    stable_releases = [r for r in releases if not r.get("prerelease", False)]
    prerelease_releases = [r for r in releases if r.get("prerelease", False)]

    if prefer_prerelease:
        # Return all, but prereleases first
        return prerelease_releases + stable_releases
    elif stable_releases:
        return stable_releases
    elif include_prerelease_if_no_stable:
        return prerelease_releases
    else:
        return []


def parse_version_code(version_name: str, version_code_str: str) -> Optional[int]:
    """
    Parse version code from release tag or version name.

    Tries multiple strategies to extract a numeric version code.

    Args:
        version_name: Version name string
        version_code_str: Version code string (if available)

    Returns:
        Integer version code or None
    """
    # Try direct parsing first
    if version_code_str:
        try:
            return int(version_code_str)
        except ValueError:
            pass

    # Try extracting from version name
    import re

    # Look for patterns like v1.2.3, 1.2.3, version-123, etc.
    patterns = [
        r"v?(\d+)\.(\d+)\.(\d+)",
        r"v?(\d+)\.(\d+)",
        r"version[-_]?(\d+)",
        r"(\d+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, version_name, re.IGNORECASE)
        if match:
            # Convert version parts to a single number
            parts = [int(g) for g in match.groups() if g]
            if len(parts) == 1:
                return parts[0]
            elif len(parts) == 2:
                return parts[0] * 1000 + parts[1]
            elif len(parts) >= 3:
                return parts[0] * 1000000 + parts[1] * 1000 + parts[2]

    return None


def get_release_download_url(release: dict[str, Any], asset_name: str) -> Optional[str]:
    """
    Get download URL for a specific asset from a release.

    Args:
        release: Release dictionary
        asset_name: Name of the asset to find

    Returns:
        Download URL or None if not found
    """
    for asset in release.get("assets", []):
        if asset.get("name") == asset_name:
            return asset.get("browser_download_url")
    return None
