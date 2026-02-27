"""
Fastlane metadata fetcher for F-Droid repository.

Fetches fastlane metadata (screenshots, descriptions, changelogs)
from upstream GitHub repositories and integrates them into the repo.
"""

import os
import tempfile
from pathlib import Path
from typing import Any, Optional

import requests


def fetch_fastlane_metadata(
    github_repo: str,
    target_dir: str,
    version_code: Optional[int] = None,
) -> dict[str, Any]:
    """
    Fetch fastlane metadata from a GitHub repository.

    Args:
        github_repo: Repository in format "owner/repo"
        target_dir: Local directory to store metadata
        version_code: Specific version code for changelog (optional)

    Returns:
        Dictionary with fetched metadata
    """
    base_url = f"https://raw.githubusercontent.com/{github_repo}"
    
    # Try different fastlane locations
    locations = [
        "HEAD/fastlane/metadata/android/en-US",
        "main/fastlane/metadata/android/en-US",
        "master/fastlane/metadata/android/en-US",
        "HEAD/metadata/en-US",
        "main/metadata/en-US",
        "master/metadata/en-US",
    ]
    
    metadata = {
        "short_description": None,
        "full_description": None,
        "title": None,
        "changelog": None,
        "screenshots": [],
        "icon": None,
        "feature_graphic": None,
    }
    
    # Try each location
    base_path = None
    for location in locations:
        test_url = f"{base_url}/{location}/short_description.txt"
        try:
            response = requests.get(test_url, timeout=10)
            if response.status_code == 200:
                base_path = location
                break
        except requests.RequestException:
            continue
    
    if not base_path:
        return metadata  # No fastlane metadata found
    
    # Fetch text files
    text_files = {
        "short_description": "short_description.txt",
        "full_description": "full_description.txt",
        "title": "title.txt",
    }
    
    for key, filename in text_files.items():
        try:
            url = f"{base_url}/{base_path}/{filename}"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                metadata[key] = response.text.strip()[:4000]  # Limit length
        except requests.RequestException:
            pass
    
    # Fetch changelog if version_code provided
    if version_code:
        try:
            url = f"{base_url}/{base_path}/changelogs/{version_code}.txt"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                metadata["changelog"] = response.text.strip()[:500]
        except requests.RequestException:
            pass
    
    # Fetch images
    image_files = {
        "icon": "images/icon.png",
        "feature_graphic": "images/featureGraphic.png",
    }
    
    for key, filename in image_files.items():
        try:
            url = f"{base_url}/{base_path}/{filename}"
            response = requests.get(url, timeout=10, stream=True)
            if response.status_code == 200:
                # Save image locally
                target_path = Path(target_dir) / "images" / f"{key}.png"
                target_path.parent.mkdir(parents=True, exist_ok=True)
                with open(target_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                metadata[key] = str(target_path)
        except requests.RequestException:
            pass
    
    # Fetch screenshots
    try:
        # First, get list of files in screenshots directory
        # This is tricky with raw GitHub API, so we try common patterns
        for i in range(1, 11):  # Try up to 10 screenshots
            for ext in ["png", "jpg", "jpeg"]:
                url = f"{base_url}/{base_path}/images/phoneScreenshots/{i}.{ext}"
                response = requests.get(url, timeout=10, stream=True)
                if response.status_code == 200:
                    target_path = Path(target_dir) / "images" / "phoneScreenshots" / f"{i}.{ext}"
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(target_path, "wb") as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            f.write(chunk)
                    metadata["screenshots"].append(str(target_path))
                    break  # Found screenshot, try next number
    except requests.RequestException:
        pass
    
    return metadata


def fetch_changelog_from_release(
    github_repo: str,
    tag_name: str,
) -> Optional[str]:
    """
    Fetch changelog from GitHub release notes.

    Args:
        github_repo: Repository in format "owner/repo"
        tag_name: Release tag name

    Returns:
        Changelog text or None
    """
    api_url = f"https://api.github.com/repos/{github_repo}/releases/tags/{tag_name}"
    
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "Fury-FDroid-Repo/1.0",
    }
    
    # Add GitHub token if available
    github_token = os.environ.get("GITHUB_TOKEN")
    if github_token:
        headers["Authorization"] = f"Bearer {github_token}"
    
    try:
        response = requests.get(api_url, headers=headers, timeout=30)
        response.raise_for_status()
        release = response.json()
        
        body = release.get("body", "")
        if body:
            # Clean up markdown slightly
            return body.strip()[:500]
    except requests.RequestException:
        pass
    
    return None


def create_fastlane_structure(
    target_dir: str,
    metadata: dict[str, Any],
) -> bool:
    """
    Create fastlane directory structure with fetched metadata.

    Args:
        target_dir: Target directory (e.g., repo/fastlane/metadata/android/en-US)
        metadata: Metadata dictionary from fetch_fastlane_metadata

    Returns:
        True if successful
    """
    base_path = Path(target_dir)
    base_path.mkdir(parents=True, exist_ok=True)
    
    # Write text files
    text_files = {
        "short_description": "short_description.txt",
        "full_description": "full_description.txt",
        "title": "title.txt",
    }
    
    for key, filename in text_files.items():
        if metadata.get(key):
            file_path = base_path / filename
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(metadata[key])
    
    # Write changelog if present
    if metadata.get("changelog"):
        changelog_path = base_path / "changelogs"
        changelog_path.mkdir(parents=True, exist_ok=True)
        # Note: versionCode should be passed separately
        # For now, skip this
    
    return True
