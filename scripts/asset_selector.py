"""
Asset selector for APK files.

Filters and selects appropriate APK assets from GitHub releases
based on configuration rules.
"""

from typing import Any, Optional


def is_valid_apk_asset(
    asset: dict[str, Any],
    include_keywords: list[str],
    exclude_keywords: list[str],
) -> bool:
    """
    Check if an asset is a valid APK file.

    Args:
        asset: Asset dictionary from GitHub API
        include_keywords: Keywords that must be present (empty = any)
        exclude_keywords: Keywords that must not be present

    Returns:
        True if asset is valid APK
    """
    name = asset.get("name", "").lower()

    # Must end with .apk
    if not name.endswith(".apk"):
        return False

    # Reject .apks (split APKs)
    if name.endswith(".apks"):
        return False

    # Check exclude keywords
    for keyword in exclude_keywords:
        if keyword.lower() in name:
            return False

    # Check include keywords (if specified, at least one must match)
    if include_keywords:
        has_include = any(kw.lower() in name for kw in include_keywords)
        if not has_include:
            return False

    return True


def extract_abi_from_filename(filename: str) -> list[str]:
    """
    Extract ABI information from APK filename.

    Args:
        filename: APK filename

    Returns:
        List of detected ABIs
    """
    name_lower = filename.lower()
    abis = []

    # Check for specific ABI markers
    if "arm64" in name_lower or "aarch64" in name_lower:
        abis.append("arm64-v8a")
    elif "armv7" in name_lower or "armeabi-v7a" in name_lower:
        abis.append("armeabi-v7a")

    if "x86_64" in name_lower:
        abis.append("x86_64")
    elif "x86" in name_lower:
        abis.append("x86")

    # Generic arm detection
    if "arm" in name_lower and not abis:
        abis.append("armeabi-v7a")

    return abis


def select_best_apk(
    assets: list[dict[str, Any]],
    include_keywords: list[str],
    exclude_keywords: list[str],
    abi_policy: str = "arm_preferred",
) -> Optional[dict[str, Any]]:
    """
    Select the best APK asset from a list.

    Args:
        assets: List of asset dictionaries
        include_keywords: Keywords that must be present
        exclude_keywords: Keywords that must not be present
        abi_policy: ABI selection policy (arm_preferred, arm64_only)

    Returns:
        Best asset dictionary or None
    """
    # Filter valid APKs
    valid_assets = [
        a for a in assets
        if is_valid_apk_asset(a, include_keywords, exclude_keywords)
    ]

    if not valid_assets:
        return None

    # Score assets based on ABI policy
    def score_asset(asset: dict[str, Any]) -> tuple[int, int]:
        """Return (abi_score, size_score) for sorting."""
        filename = asset.get("name", "")
        abis = extract_abi_from_filename(filename)
        size = asset.get("size", 0)

        abi_score = 0
        if abi_policy == "arm64_only":
            if "arm64-v8a" in abis:
                abi_score = 2
            elif "armeabi-v7a" in abis:
                abi_score = 1
            else:
                abi_score = 0  # x86 or unknown
        else:  # arm_preferred
            if "arm64-v8a" in abis:
                abi_score = 2
            elif "armeabi-v7a" in abis:
                abi_score = 1
            elif "x86_64" in abis:
                abi_score = 0
            elif "x86" in abis:
                abi_score = 0
            else:
                abi_score = 1  # Universal/no ABI specified

        return (abi_score, size)

    # Sort by ABI score (desc), then size (desc)
    valid_assets.sort(key=score_asset, reverse=True)

    return valid_assets[0] if valid_assets else None


def get_all_apk_assets(
    release: dict[str, Any],
    include_keywords: list[str],
    exclude_keywords: list[str],
) -> list[dict[str, Any]]:
    """
    Get all valid APK assets from a release.

    Args:
        release: Release dictionary
        include_keywords: Keywords that must be present
        exclude_keywords: Keywords that must not be present

    Returns:
        List of valid APK asset dictionaries
    """
    assets = release.get("assets", [])
    return [
        a for a in assets
        if is_valid_apk_asset(a, include_keywords, exclude_keywords)
    ]


def check_abi_compliance(
    asset: dict[str, Any],
    abi_policy: str,
) -> tuple[bool, list[str]]:
    """
    Check if an asset complies with ABI policy.

    Args:
        asset: Asset dictionary
        abi_policy: ABI policy (arm_preferred, arm64_only)

    Returns:
        Tuple of (is_compliant, list of detected ABIs)
    """
    filename = asset.get("name", "")
    abis = extract_abi_from_filename(filename)

    # Reject x86 builds
    if "x86" in abis or "x86_64" in abis:
        return (False, abis)

    # If arm64_only policy, require arm64-v8a
    if abi_policy == "arm64_only":
        if abis and "arm64-v8a" not in abis:
            return (False, abis)

    return (True, abis)
