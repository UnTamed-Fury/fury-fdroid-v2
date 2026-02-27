"""
APK metadata extraction using aapt (Android Asset Packaging Tool).

Uses system aapt command for fast, reliable APK metadata extraction.
Much lighter than androguard and more accurate than pyaxmlparser.
"""

import hashlib
import os
import re
import subprocess
import tempfile
import zipfile
from typing import Any, Optional

import requests


def download_apk(url: str, timeout: int = 300) -> tuple[str, int]:
    """Download APK file to temporary location."""
    try:
        response = requests.get(url, timeout=timeout, stream=True)
        response.raise_for_status()
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
    """Compute SHA256 hash of a file."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()


def extract_native_code_from_apk(file_path: str) -> list[str]:
    """Extract native code ABIs by parsing lib/ directory in APK."""
    abis = set()
    try:
        with zipfile.ZipFile(file_path, 'r') as zip_ref:
            for filename in zip_ref.namelist():
                if filename.startswith('lib/'):
                    parts = filename.split('/')
                    if len(parts) >= 2:
                        abi = parts[1]
                        if abi in ['arm64-v8a', 'armeabi-v7a', 'armeabi', 'x86', 'x86_64']:
                            abis.add(abi)
    except Exception:
        pass
    return list(abis)


def run_aapt_command(file_path: str, args: list[str]) -> str:
    """Run aapt command and return output."""
    cmd = ["aapt"] + args + [file_path]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            raise RuntimeError(f"aapt failed: {result.stderr}")
        return result.stdout
    except subprocess.TimeoutExpired:
        raise RuntimeError("aapt command timed out")
    except FileNotFoundError:
        raise RuntimeError("aapt command not found - install android-tools package")


def parse_aapt_dump_badging(output: str) -> dict[str, Any]:
    """Parse aapt dump badging output."""
    metadata = {
        "package_name": "",
        "version_name": "",
        "version_code": 0,
        "min_sdk_version": 0,
        "target_sdk_version": 0,
        "permissions": [],
        "native_code": [],
    }

    # Package info: package: name='com.example.app' versionCode='100' versionName='1.0.0'
    pkg_match = re.search(r"package: name='([^']+)' versionCode='(\d+)' versionName='([^']+)'", output)
    if pkg_match:
        metadata["package_name"] = pkg_match.group(1)
        metadata["version_code"] = int(pkg_match.group(2))
        metadata["version_name"] = pkg_match.group(3)

    # SDK versions: sdkVersion:'21' targetSdkVersion:'34'
    sdk_match = re.search(r"sdkVersion:'(\d+)'", output)
    if sdk_match:
        metadata["min_sdk_version"] = int(sdk_match.group(1))

    target_sdk_match = re.search(r"targetSdkVersion:'(\d+)'", output)
    if target_sdk_match:
        metadata["target_sdk_version"] = int(target_sdk_match.group(1))

    # Permissions: uses-permission: name='android.permission.INTERNET'
    for perm_match in re.finditer(r"uses-permission: name='([^']+)'", output):
        metadata["permissions"].append({"name": perm_match.group(1)})

    # Native code: native-code: 'arm64-v8a', 'armeabi-v7a'
    native_match = re.search(r"native-code: (.+)", output)
    if native_match:
        native_str = native_match.group(1)
        for abi_match in re.finditer(r"'([^']+)'", native_str):
            abi = abi_match.group(1)
            if abi in ['arm64-v8a', 'armeabi-v7a', 'armeabi', 'x86', 'x86_64']:
                metadata["native_code"].append(abi)

    return metadata


def extract_apk_metadata(file_path: str) -> dict[str, Any]:
    """Extract metadata from APK file using aapt."""
    try:
        badging_output = run_aapt_command(file_path, ["dump", "badging"])
    except RuntimeError as e:
        raise RuntimeError(f"Failed to run aapt: {e}") from None

    metadata = parse_aapt_dump_badging(badging_output)

    if not metadata["native_code"]:
        metadata["native_code"] = extract_native_code_from_apk(file_path)

    signing_cert = None  # aapt doesn't provide signing certificate

    return {
        "package_name": metadata["package_name"],
        "version_name": metadata["version_name"],
        "version_code": metadata["version_code"],
        "min_sdk_version": metadata["min_sdk_version"],
        "target_sdk_version": metadata["target_sdk_version"],
        "permissions": metadata["permissions"],
        "native_code": metadata["native_code"],
        "signing_cert_sha256": signing_cert,
    }


def process_apk(download_url: str, cleanup: bool = True) -> dict[str, Any]:
    """Download and process APK file."""
    temp_path = None
    try:
        temp_path, file_size = download_apk(download_url)
        metadata = extract_apk_metadata(temp_path)
        sha256 = compute_sha256(temp_path)
        return {
            **metadata,
            "sha256": sha256,
            "size": file_size,
            "download_url": download_url,
        }
    finally:
        if cleanup and temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except OSError:
                pass


def extract_metadata_from_bytes(apk_bytes: bytes) -> dict[str, Any]:
    """Extract metadata from APK bytes."""
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
