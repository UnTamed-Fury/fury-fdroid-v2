"""
APK metadata extraction using lightweight tools.

Uses pyaxmlparser for manifest parsing instead of heavy androguard.
Much faster installation and execution.
"""

import hashlib
import os
import tempfile
import zipfile
from typing import Any, Optional

import requests
from pyaxmlparser import APK


def download_apk(url: str, timeout: int = 300) -> tuple[str, int]:
    """
    Download APK file to temporary location.

    Args:
        url: Download URL
        timeout: Request timeout in seconds

    Returns:
        Tuple of (temporary file path, file size in bytes)

    Raises:
        RuntimeError: If download fails
    """
    try:
        response = requests.get(url, timeout=timeout, stream=True)
        response.raise_for_status()

        # Create temporary file
        fd, temp_path = tempfile.mkstemp(suffix=".apk")
        total_size = 0

        with os.fdopen(fd, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    total_size += len(chunk)

        return temp_path, total_size

    except requests.RequestException as e:
        raise RuntimeError(f"Failed to download APK: {e}") from e


def compute_sha256(file_path: str) -> str:
    """
    Compute SHA256 hash of a file.

    Args:
        file_path: Path to file

    Returns:
        SHA256 hash as hex string
    """
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()


def extract_native_code_from_apk(file_path: str) -> list[str]:
    """
    Extract native code ABIs by parsing lib/ directory in APK.

    Args:
        file_path: Path to APK file

    Returns:
        List of detected ABIs
    """
    abis = set()
    try:
        with zipfile.ZipFile(file_path, 'r') as zip_ref:
            for filename in zip_ref.namelist():
                if filename.startswith('lib/'):
                    parts = filename.split('/')
                    if len(parts) >= 2:
                        abi = parts[1]
                        # Filter valid ABIs
                        if abi in ['arm64-v8a', 'armeabi-v7a', 'armeabi', 'x86', 'x86_64']:
                            abis.add(abi)
    except Exception:
        pass
    return list(abis)


def extract_apk_metadata(file_path: str) -> dict[str, Any]:
    """
    Extract metadata from APK file using pyaxmlparser.

    Args:
        file_path: Path to APK file

    Returns:
        Dictionary containing extracted metadata

    Raises:
        RuntimeError: If extraction fails
    """
    try:
        apk = APK(file_path)
    except Exception as e:
        raise RuntimeError(f"Failed to parse APK: {e}") from None

    # Extract package information
    package_name = apk.package

    # Extract version information
    version_name = apk.version_name
    version_code = apk.version_code

    # Extract SDK versions
    min_sdk = apk.min_sdk_version
    target_sdk = apk.target_sdk_version

    # Extract permissions
    permissions = []
    for perm in apk.get_permissions():
        permissions.append({"name": perm})

    # Extract native code ABIs (parse lib/ directory)
    native_code = extract_native_code_from_apk(file_path)

    # Note: pyaxmlparser doesn't provide signing certificate
    # For signature verification, would need apksigner or jarsigner
    signing_cert = None

    return {
        "package_name": package_name or "",
        "version_name": version_name or "",
        "version_code": version_code or 0,
        "min_sdk_version": min_sdk or 0,
        "target_sdk_version": target_sdk or 0,
        "permissions": permissions,
        "native_code": native_code,
        "signing_cert_sha256": signing_cert,
    }


def process_apk(
    download_url: str,
    cleanup: bool = True,
) -> dict[str, Any]:
    """
    Download and process APK file.

    Args:
        download_url: URL to download APK from
        cleanup: Whether to delete temporary file after processing

    Returns:
        Dictionary containing all extracted metadata including hash and size

    Raises:
        RuntimeError: If processing fails
    """
    temp_path = None
    try:
        # Download APK
        temp_path, file_size = download_apk(download_url)

        # Extract metadata
        metadata = extract_apk_metadata(temp_path)

        # Compute hash
        sha256 = compute_sha256(temp_path)

        # Combine all information
        result = {
            **metadata,
            "sha256": sha256,
            "size": file_size,
            "download_url": download_url,
        }

        return result

    finally:
        # Clean up temporary file
        if cleanup and temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except OSError:
                pass  # Ignore cleanup errors


def extract_metadata_from_bytes(apk_bytes: bytes) -> dict[str, Any]:
    """
    Extract metadata from APK bytes (without writing to disk).

    Args:
        apk_bytes: Raw APK file bytes

    Returns:
        Dictionary containing extracted metadata
    """
    # Write to temp file for pyaxmlparser (it requires file path)
    fd, temp_path = tempfile.mkstemp(suffix=".apk")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(apk_bytes)

        return extract_apk_metadata(temp_path)

    finally:
        try:
            os.unlink(temp_path)
        except OSError:
            pass
