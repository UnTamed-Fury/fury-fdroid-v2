#!/usr/bin/env python3
"""
Main orchestrator for F-Droid repository builder.

Coordinates all modules to:
1. Load configuration from apps.yaml
2. Fetch and process releases from GitHub
3. Validate APKs
4. Build index-v2.json
5. Update metadata cache
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Optional

import yaml

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent))

from fetch_releases import fetch_releases
from asset_selector import select_best_apk, check_abi_compliance
from apk_processor import process_apk
from validator import AppValidator, GlobalValidator
from index_builder import (
    build_index,
    build_index_v1,
    build_package_object,
    build_version_object,
    apply_retention,
    write_index,
    write_index_v1,
    validate_index_structure,
)
from reporter import Reporter


def load_yaml_config(config_path: str) -> dict[str, Any]:
    """Load and parse YAML configuration."""
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_metadata_cache(cache_path: str) -> dict[str, Any]:
    """Load metadata cache from JSON file."""
    if not os.path.exists(cache_path):
        return {"apps": {}}

    with open(cache_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_metadata_cache(cache: dict[str, Any], cache_path: str) -> None:
    """Save metadata cache to JSON file."""
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2)
        f.write("\n")


def process_app(
    app_config: dict[str, Any],
    cache: dict[str, Any],
    global_validator: GlobalValidator,
    reporter: Reporter,
) -> Optional[dict[str, Any]]:
    """
    Process a single app configuration.

    Args:
        app_config: App configuration from apps.yaml
        cache: Metadata cache
        global_validator: Global validator for cross-app checks
        reporter: Reporter for errors/warnings

    Returns:
        Package object for index, or None if failed
    """
    logical_id = app_config.get("logical_id", "")
    github_repo = app_config.get("github", "")

    if not logical_id or not github_repo:
        reporter.error(
            f"Missing logical_id or github for app config",
            logical_id=logical_id or "unknown",
        )
        return None

    reporter.notice(f"Processing {logical_id} ({github_repo})")

    # Get app-specific configuration
    release_config = app_config.get("release", {})
    package_config = app_config.get("package", {})
    signature_config = app_config.get("signature", {})
    abi_policy = app_config.get("abi_policy", "arm_preferred")
    retention_config = app_config.get("retention", {})
    asset_filter = app_config.get("asset_filter", {})
    metadata_config = app_config.get("metadata", {})

    # Get cached data
    cached_app = cache.get("apps", {}).get(logical_id, {})
    cached_cert = cached_app.get("signing_cert")
    cached_highest_version = cached_app.get("highest_versionCode")

    # Create app validator
    app_validator = AppValidator(
        logical_id=logical_id,
        abi_policy=abi_policy,
        allowed_ids=package_config.get("allowed_ids", []),
        allow_pkg_change=package_config.get("allow_pkg_change", False),
        allow_signature_change=signature_config.get("allow_signature_change", False),
        cached_cert=cached_cert,
        cached_highest_version=cached_highest_version,
    )

    # Fetch releases
    try:
        releases = fetch_releases(
            github_repo=github_repo,
            ignore_drafts=release_config.get("ignore_drafts", True),
            prefer_prerelease=release_config.get("prefer_prerelease", False),
            include_prerelease_if_no_stable=release_config.get(
                "include_prerelease_if_no_stable", True
            ),
        )
    except RuntimeError as e:
        reporter.error(str(e), logical_id=logical_id)
        return None

    if not releases:
        reporter.error("No valid releases found", logical_id=logical_id)
        return None

    # Process each release
    valid_versions = []
    new_highest_version = None
    new_signing_cert = None

    for release in releases:
        release_name = release.get("tag_name", release.get("name", "unknown"))

        # Select best APK asset
        asset = select_best_apk(
            assets=release.get("assets", []),
            include_keywords=asset_filter.get("include_keywords", []),
            exclude_keywords=asset_filter.get("exclude_keywords", []),
            abi_policy=abi_policy,
        )

        if not asset:
            reporter.warning(
                f"No valid APK asset in release {release_name}",
                logical_id=logical_id,
            )
            continue

        # Check ABI compliance
        is_compliant, detected_abis = check_abi_compliance(asset, abi_policy)
        if not is_compliant:
            reporter.warning(
                f"Release {release_name} has non-compliant ABI: {detected_abis}",
                logical_id=logical_id,
            )
            continue

        # Get download URL
        download_url = asset.get("browser_download_url")
        if not download_url:
            reporter.warning(
                f"No download URL for asset in release {release_name}",
                logical_id=logical_id,
            )
            continue

        # Process APK
        try:
            metadata = process_apk(download_url, cleanup=True)
        except RuntimeError as e:
            reporter.warning(
                f"Failed to process APK from {release_name}: {e}",
                logical_id=logical_id,
            )
            continue

        # Validate APK
        result = app_validator.validate_version(metadata)
        if not result.is_valid:
            reporter.warning(
                f"Validation failed for {release_name}: {result.error_message}",
                logical_id=logical_id,
            )
            continue

        # Track highest version and signing cert
        version_code = metadata.get("version_code")
        if version_code is not None:
            if new_highest_version is None or version_code > new_highest_version:
                new_highest_version = version_code

        if metadata.get("signing_cert_sha256"):
            new_signing_cert = metadata.get("signing_cert_sha256")

        # Build version object
        version_obj = build_version_object(metadata, download_url)
        valid_versions.append(version_obj)

    # Check if we have any valid versions
    if not valid_versions:
        reporter.error("No valid versions found after validation", logical_id=logical_id)
        return None

    # Get package ID from first valid version
    package_id = None
    for v in valid_versions:
        pkg = v.get("manifest", {}).get("packageName")
        if pkg:
            package_id = pkg
            break

    if not package_id:
        # Try to get from allowed_ids
        allowed_ids = package_config.get("allowed_ids", [])
        if allowed_ids:
            package_id = allowed_ids[0]
        else:
            reporter.error("Could not determine package ID", logical_id=logical_id)
            return None

    # Register with global validator
    result = global_validator.register_package_id(package_id, logical_id)
    if not result.is_valid:
        reporter.error(result.error_message, logical_id=logical_id)
        return None

    # Apply retention policy
    retain_count = retention_config.get(
        "retain_versions",
        cache.get("repo", {}).get("max_versions_default", 2),
    )
    valid_versions = apply_retention(valid_versions, retain_count)

    # Update cache for this app
    if new_highest_version is not None or new_signing_cert:
        cache["apps"][logical_id] = {
            "package_id": package_id,
            "signing_cert": new_signing_cert or cached_cert,
            "highest_versionCode": new_highest_version or cached_highest_version,
        }

    # Build package object
    package_obj = build_package_object(
        package_id=package_id,
        versions=valid_versions,
        app_config=app_config,
    )

    reporter.notice(
        f"Successfully processed {logical_id}: {len(valid_versions)} version(s)",
        logical_id=logical_id,
    )

    return package_obj


def main() -> int:
    """Main entry point."""
    # Determine paths
    base_dir = Path(__file__).parent.parent
    config_path = base_dir / "apps.yaml"
    cache_path = base_dir / "metadata_cache.json"
    output_path = base_dir / "repo" / "index-v2.json"

    # Initialize reporter
    reporter = Reporter()

    # Load configuration
    try:
        config = load_yaml_config(str(config_path))
    except Exception as e:
        reporter.error(f"Failed to load apps.yaml: {e}")
        reporter.print_summary()
        return 1

    # Load metadata cache
    cache = load_metadata_cache(str(cache_path))

    # Get repo configuration
    repo_config = config.get("repo", {})
    apps_config = config.get("apps", [])

    if not apps_config:
        reporter.error("No apps defined in apps.yaml")
        reporter.print_summary()
        return 1

    # Initialize global validator
    global_validator = GlobalValidator()

    # Process each app
    packages_data = {}

    for app_config in apps_config:
        package_obj = process_app(
            app_config=app_config,
            cache=cache,
            global_validator=global_validator,
            reporter=reporter,
        )

        if package_obj:
            # Get package ID from package_obj metadata
            pkg_id = None
            for v in package_obj.get("versions", {}).values():
                pkg_id = v.get("manifest", {}).get("packageName")
                if pkg_id:
                    break

            if pkg_id:
                packages_data[pkg_id] = package_obj

    # Check for duplicate package IDs
    duplicate_pairs = global_validator.get_duplicate_apps()
    for pkg_id, logical_id1, logical_id2 in duplicate_pairs:
        reporter.error(
            f"Duplicate package ID '{pkg_id}' between '{logical_id1}' and '{logical_id2}'",
        )
        # Remove both from packages_data
        # (They shouldn't be in there since we didn't add duplicates)

    # Build final index
    index = build_index(repo_config, packages_data)

    # Validate index structure
    is_valid, errors = validate_index_structure(index)
    if not is_valid:
        for error in errors:
            reporter.error(f"Index validation failed: {error}")
        reporter.print_summary()
        return 1

    # Write index-v2.json
    try:
        write_index(index, str(output_path))
        reporter.notice(f"Successfully wrote index-v2.json with {len(packages_data)} package(s)")
    except Exception as e:
        reporter.error(f"Failed to write index-v2.json: {e}")
        reporter.print_summary()
        return 1

    # Write index-v1.json
    output_path_v1 = base_dir / "repo" / "index-v1.json"
    try:
        index_v1 = build_index_v1(repo_config, packages_data)
        write_index_v1(index_v1, str(output_path_v1))
        reporter.notice(f"Successfully wrote index-v1.json with {len(index_v1.get('packages', []))} package(s)")
    except Exception as e:
        reporter.error(f"Failed to write index-v1.json: {e}")
        reporter.print_summary()
        return 1

    # Save updated cache
    try:
        save_metadata_cache(cache, str(cache_path))
    except Exception as e:
        reporter.warning(f"Failed to save metadata cache: {e}")

    # Print summary
    reporter.print_summary()

    # Return non-zero if any app failed (but index was generated)
    if reporter.has_failures():
        return 2  # Partial success

    return 0


if __name__ == "__main__":
    sys.exit(main())
