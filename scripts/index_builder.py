"""
Index builder for F-Droid index-v2.json.

Constructs the final index file following the official F-Droid
index-v2.json structure.
"""

import json
import time
from typing import Any, Optional


def get_current_timestamp_ms() -> int:
    """Get current Unix timestamp in milliseconds."""
    return int(time.time() * 1000)


def build_repo_object(
    name: dict[str, str],
    description: dict[str, str],
    url: str,
    icon: Optional[str] = None,
) -> dict[str, Any]:
    """
    Build the repo object for index-v2.json.

    Args:
        name: Localized name dict
        description: Localized description dict
        url: Repository URL
        icon: Icon URL (optional)

    Returns:
        Repo object dictionary
    """
    repo = {
        "name": name,
        "description": description,
        "address": url,
        "timestamp": get_current_timestamp_ms(),
    }

    if icon:
        repo["icon"] = icon

    return repo


def build_version_object(
    metadata: dict[str, Any],
    download_url: str,
    added_timestamp: Optional[int] = None,
) -> dict[str, Any]:
    """
    Build a version object for the versions dict.

    Args:
        metadata: Extracted APK metadata
        download_url: Direct download URL (or relative path)
        added_timestamp: When this version was added (optional)

    Returns:
        Version object dictionary
    """
    if added_timestamp is None:
        added_timestamp = get_current_timestamp_ms()

    version = {
        "added": added_timestamp,
        "file": {
            "name": download_url,
            "sha256": metadata.get("sha256", ""),
            "size": metadata.get("size", 0),
        },
        "manifest": {
            "versionName": metadata.get("version_name", ""),
            "versionCode": metadata.get("version_code", 0),
            "usesSdk": {
                "minSdkVersion": metadata.get("min_sdk_version", 0),
                "targetSdkVersion": metadata.get("target_sdk_version", 0),
            },
            "signer": {
                "sha256": [metadata.get("signing_cert_sha256", "")]
            } if metadata.get("signing_cert_sha256") else {},
        },
    }

    # Add native code ABIs if present
    native_code = metadata.get("native_code", [])
    if native_code:
        version["manifest"]["nativecode"] = native_code

    # Add permissions if present
    permissions = metadata.get("permissions", [])
    if permissions:
        version["manifest"]["usesPermission"] = permissions

    return version


def build_package_object(
    package_id: str,
    versions: list[dict[str, Any]],
    app_config: dict[str, Any],
    added_timestamp: Optional[int] = None,
) -> dict[str, Any]:
    """
    Build a package object for the packages dict.

    Args:
        package_id: Package ID (e.g., com.example.app)
        versions: List of version objects
        app_config: App configuration from apps.yaml
        added_timestamp: When this package was added (optional)

    Returns:
        Package object dictionary
    """
    if added_timestamp is None:
        added_timestamp = get_current_timestamp_ms()

    # Get metadata from app config
    metadata_config = app_config.get("metadata", {})

    # Build metadata section
    metadata = {
        "added": added_timestamp,
        "lastUpdated": get_current_timestamp_ms(),
    }

    # Add categories
    categories = metadata_config.get("categories", [])
    if categories:
        metadata["categories"] = categories

    # Add license
    license_str = metadata_config.get("license", "")
    if license_str:
        metadata["license"] = license_str

    # Add source URL
    source_url = metadata_config.get("source_url", "")
    if source_url:
        metadata["sourceCode"] = source_url

    # Add issue tracker
    issue_tracker = metadata_config.get("issue_tracker", "")
    if issue_tracker:
        metadata["issueTracker"] = issue_tracker

    # Add anti-features
    anti_features = metadata_config.get("anti_features", [])
    if anti_features:
        metadata["antiFeatures"] = anti_features

    # Add preferred signer (from first/last version)
    if versions:
        signer = versions[0].get("manifest", {}).get("signer", {})
        signer_sha = signer.get("sha256", [])
        if signer_sha:
            metadata["preferredSigner"] = signer_sha[0]

    # Build versions dict keyed by SHA256
    versions_dict = {}
    for v in versions:
        sha256 = v.get("file", {}).get("sha256", "")
        if sha256:
            versions_dict[sha256] = v

    return {
        "metadata": metadata,
        "versions": versions_dict,
    }


def apply_retention(
    versions: list[dict[str, Any]],
    retain_count: int,
) -> list[dict[str, Any]]:
    """
    Apply version retention policy.

    Args:
        versions: List of version objects
        retain_count: Number of versions to keep

    Returns:
        Filtered list of versions
    """
    if not versions or retain_count <= 0:
        return []

    # Sort by versionCode descending
    sorted_versions = sorted(
        versions,
        key=lambda v: v.get("manifest", {}).get("versionCode", 0),
        reverse=True,
    )

    return sorted_versions[:retain_count]


def build_index(
    repo_config: dict[str, Any],
    packages_data: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """
    Build the complete index-v2.json structure.

    Args:
        repo_config: Repository configuration
        packages_data: Dict of package_id -> package_object

    Returns:
        Complete index dictionary
    """
    index = {
        "repo": build_repo_object(
            name=repo_config.get("name", {"en-US": "F-Droid Repo"}),
            description=repo_config.get("description", {"en-US": "F-Droid Repository"}),
            url=repo_config.get("url", ""),
            icon=repo_config.get("icon"),
        ),
        "packages": packages_data,
    }

    return index


def build_index_v1(
    repo_config: dict[str, Any],
    packages_data: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """
    Build the index-v1.json structure (simplified format).

    index-v1.json contains a list of packages with their latest version info.

    Args:
        repo_config: Repository configuration
        packages_data: Dict of package_id -> package_object

    Returns:
        index-v1 dictionary
    """
    packages_list = []

    for package_id, package_obj in packages_data.items():
        metadata = package_obj.get("metadata", {})
        versions = package_obj.get("versions", {})

        # Get the latest version (highest versionCode)
        latest_version = None
        latest_version_code = -1

        for sha256, version_obj in versions.items():
            manifest = version_obj.get("manifest", {})
            version_code = manifest.get("versionCode", 0)
            if version_code > latest_version_code:
                latest_version_code = version_code
                latest_version = version_obj

        if latest_version:
            manifest = latest_version.get("manifest", {})
            file_info = latest_version.get("file", {})

            package_entry = {
                "packageName": package_id,
                "versionName": manifest.get("versionName", ""),
                "versionCode": manifest.get("versionCode", 0),
                "size": file_info.get("size", 0),
                "hash": file_info.get("sha256", ""),
                "hashType": "sha256",
            }

            # Add minSdkVersion if available
            uses_sdk = manifest.get("usesSdk", {})
            if uses_sdk.get("minSdkVersion"):
                package_entry["minSdkVersion"] = uses_sdk["minSdkVersion"]

            # Add targetSdkVersion if available
            if uses_sdk.get("targetSdkVersion"):
                package_entry["targetSdkVersion"] = uses_sdk["targetSdkVersion"]

            # Add nativecode if available
            if manifest.get("nativecode"):
                package_entry["nativecode"] = manifest["nativecode"]

            # Add signer if available
            signer = manifest.get("signer", {})
            if signer.get("sha256"):
                package_entry["sig"] = signer["sha256"][0]

            packages_list.append(package_entry)

    index_v1 = {
        "packages": packages_list,
    }

    return index_v1


def write_index(
    index: dict[str, Any],
    output_path: str,
    indent: int = 2,
) -> None:
    """
    Write index to JSON file.

    Args:
        index: Index dictionary
        output_path: Output file path
        indent: JSON indentation level
    """
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=indent, ensure_ascii=False)
        f.write("\n")  # Trailing newline


def write_index_v1(
    index_v1: dict[str, Any],
    output_path: str,
    indent: int = None,
) -> None:
    """
    Write index-v1.json to JSON file (compact format).

    Args:
        index_v1: index-v1 dictionary
        output_path: Output file path
        indent: JSON indentation level (None for compact)
    """
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(index_v1, f, indent=indent, ensure_ascii=False, separators=(',', ':'))
        f.write("\n")  # Trailing newline


def validate_index_structure(index: dict[str, Any]) -> tuple[bool, list[str]]:
    """
    Validate index structure before writing.

    Args:
        index: Index dictionary

    Returns:
        Tuple of (is_valid, list of errors)
    """
    errors = []

    # Check repo object
    if "repo" not in index:
        errors.append("Missing 'repo' object")
    else:
        repo = index["repo"]
        if "name" not in repo:
            errors.append("Missing repo.name")
        if "description" not in repo:
            errors.append("Missing repo.description")
        if "address" not in repo:
            errors.append("Missing repo.address")
        if "timestamp" not in repo:
            errors.append("Missing repo.timestamp")

    # Check packages object
    if "packages" not in index:
        errors.append("Missing 'packages' object")
    elif not isinstance(index["packages"], dict):
        errors.append("'packages' must be an object")

    return (len(errors) == 0, errors)
