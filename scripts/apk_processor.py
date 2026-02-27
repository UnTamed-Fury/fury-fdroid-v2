"""
APK metadata extraction using androguard.

Extracts package information, version details, permissions,
and signing certificates from APK files.
"""

import hashlib
import os
import tempfile
from typing import Any, Optional

import requests


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


def extract_apk_metadata(file_path: str) -> dict[str, Any]:
    """
    Extract metadata from APK file using androguard.

    Args:
        file_path: Path to APK file

    Returns:
        Dictionary containing extracted metadata

    Raises:
        RuntimeError: If extraction fails
    """
    # Try androguard 4.x first, then fall back to 3.x
    try:
        from androguard.core.apk import APK  # androguard 4.x
    except ImportError:
        try:
            from androguard.core.bytecodes.apk import APK  # androguard 3.x
        except ImportError:
            raise RuntimeError("androguard is not installed - run: pip install androguard") from None

    try:
        apk = APK(file_path)
    except Exception as e:
        raise RuntimeError(f"Failed to parse APK: {e}") from e

    # Extract package information
    package_name = apk.get_package()

    # Extract version information
    version_name = apk.get_androidversion_name()
    version_code = apk.get_androidversion_code()

    # Extract SDK versions
    min_sdk = apk.get_min_sdk_version()
    target_sdk = apk.get_target_sdk_version()

    # Extract permissions
    permissions = []
    for perm in apk.get_permissions():
        permissions.append({"name": perm})

    # Extract native code ABIs
    native_code = apk.get_native_code() or []

    # Extract signing certificate
    signing_cert = None
    try:
        certificates = apk.get_certificates()
        if certificates:
            # Use the first certificate
            cert = certificates[0]
            # Get SHA256 fingerprint
            signing_cert = hashlib.sha256(cert.get_der()).hexdigest()
    except Exception:
        pass

    return {
        "package_name": package_name,
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
    # Try androguard 4.x first, then fall back to 3.x
    try:
        from androguard.core.apk import APK  # androguard 4.x
    except ImportError:
        try:
            from androguard.core.bytecodes.apk import APK  # androguard 3.x
        except ImportError:
            raise RuntimeError("androguard is not installed") from None

    # Write to temp file for androguard (it requires file path)
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
