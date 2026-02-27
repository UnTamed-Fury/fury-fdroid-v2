"""
Validation rules for APK metadata.

Implements all validation checks including ABI, signature,
package ID, version code, and duplicate detection.
"""

from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class ValidationResult:
    """Result of a validation check."""

    is_valid: bool
    error_message: str = ""
    warning_message: str = ""


def validate_abi(
    metadata: dict[str, Any],
    abi_policy: str,
) -> ValidationResult:
    """
    Validate ABI compliance.

    Args:
        metadata: Extracted APK metadata
        abi_policy: Policy (arm_preferred, arm64_only)

    Returns:
        ValidationResult
    """
    native_code = metadata.get("native_code", [])

    # Check for x86 ABIs
    if "x86" in native_code or "x86_64" in native_code:
        return ValidationResult(
            is_valid=False,
            error_message="x86 or x86_64 build detected - ARM only repository"
        )

    # If arm64_only policy, require arm64-v8a
    if abi_policy == "arm64_only":
        if native_code and "arm64-v8a" not in native_code:
            return ValidationResult(
                is_valid=False,
                error_message=f"arm64_only policy requires arm64-v8a, found: {native_code}"
            )

    return ValidationResult(is_valid=True)


def validate_package_id(
    metadata: dict[str, Any],
    allowed_ids: list[str],
) -> ValidationResult:
    """
    Validate package ID against allowed list.

    Args:
        metadata: Extracted APK metadata
        allowed_ids: List of allowed package IDs

    Returns:
        ValidationResult
    """
    package_name = metadata.get("package_name", "")

    if not package_name:
        return ValidationResult(
            is_valid=False,
            error_message="No package name found in APK"
        )

    if allowed_ids and package_name not in allowed_ids:
        return ValidationResult(
            is_valid=False,
            error_message=f"Package ID '{package_name}' not in allowed list: {allowed_ids}"
        )

    return ValidationResult(is_valid=True)


def validate_signature(
    metadata: dict[str, Any],
    cached_cert: Optional[str],
    allow_signature_change: bool,
) -> ValidationResult:
    """
    Validate signing certificate.

    Note: Signing certificate extraction requires androguard or apksigner.
    If not available, signature validation is skipped (warning only).

    Args:
        metadata: Extracted APK metadata
        cached_cert: Previously cached certificate (if any)
        allow_signature_change: Whether signature changes are allowed

    Returns:
        ValidationResult
    """
    current_cert = metadata.get("signing_cert_sha256")

    # Skip signature validation if cert not available (pyaxmlparser doesn't extract it)
    if not current_cert:
        return ValidationResult(
            is_valid=True,
            warning_message="Signing certificate not extracted (requires androguard/apksigner)"
        )

    if cached_cert and current_cert != cached_cert:
        if not allow_signature_change:
            return ValidationResult(
                is_valid=False,
                error_message="Signing certificate changed and allow_signature_change=false"
            )
        else:
            return ValidationResult(
                is_valid=True,
                warning_message="Signing certificate changed (allowed by policy)"
            )

    return ValidationResult(is_valid=True)


def validate_version_code(
    version_code: int,
    cached_highest_version: Optional[int],
) -> ValidationResult:
    """
    Validate version code (no downgrades).

    Args:
        version_code: Current version code
        cached_highest_version: Highest known version code

    Returns:
        ValidationResult
    """
    if cached_highest_version is not None:
        if version_code < cached_highest_version:
            return ValidationResult(
                is_valid=False,
                error_message=f"Version code {version_code} is less than cached highest {cached_highest_version}"
            )

    return ValidationResult(is_valid=True)


def validate_duplicate_version_code(
    version_code: int,
    existing_version_codes: set[int],
) -> ValidationResult:
    """
    Check for duplicate version codes.

    Args:
        version_code: Current version code
        existing_version_codes: Set of already seen version codes

    Returns:
        ValidationResult
    """
    if version_code in existing_version_codes:
        return ValidationResult(
            is_valid=False,
            error_message=f"Duplicate version code: {version_code}"
        )

    return ValidationResult(is_valid=True)


def validate_duplicate_package_id(
    package_id: str,
    package_id_map: dict[str, str],
    current_logical_id: str,
) -> ValidationResult:
    """
    Check for duplicate package IDs across different logical apps.

    Args:
        package_id: Current package ID
        package_id_map: Map of package_id -> logical_id
        current_logical_id: Current logical app ID

    Returns:
        ValidationResult
    """
    if package_id in package_id_map:
        existing_logical_id = package_id_map[package_id]
        if existing_logical_id != current_logical_id:
            return ValidationResult(
                is_valid=False,
                error_message=f"Duplicate package ID '{package_id}' used by both '{existing_logical_id}' and '{current_logical_id}'"
            )

    return ValidationResult(is_valid=True)


def validate_hash(
    computed_hash: str,
    expected_hash: Optional[str],
) -> ValidationResult:
    """
    Validate APK hash matches expected value.

    Args:
        computed_hash: Computed SHA256 hash
        expected_hash: Expected hash (if any)

    Returns:
        ValidationResult
    """
    if expected_hash and computed_hash != expected_hash:
        return ValidationResult(
            is_valid=False,
            error_message=f"Hash mismatch: computed {computed_hash}, expected {expected_hash}"
        )

    return ValidationResult(is_valid=True)


class AppValidator:
    """
    Validator for a single app configuration.

    Maintains state for version tracking and duplicate detection.
    """

    def __init__(
        self,
        logical_id: str,
        abi_policy: str = "arm_preferred",
        allowed_ids: Optional[list[str]] = None,
        allow_pkg_change: bool = False,
        allow_signature_change: bool = False,
        cached_cert: Optional[str] = None,
        cached_highest_version: Optional[int] = None,
    ):
        self.logical_id = logical_id
        self.abi_policy = abi_policy
        self.allowed_ids = allowed_ids or []
        self.allow_pkg_change = allow_pkg_change
        self.allow_signature_change = allow_signature_change
        self.cached_cert = cached_cert
        self.cached_highest_version = cached_highest_version
        self.seen_version_codes: set[int] = set()
        self.validation_errors: list[str] = []
        self.validation_warnings: list[str] = []

    def validate_version(
        self,
        metadata: dict[str, Any],
    ) -> ValidationResult:
        """
        Validate a single version of the app.

        Args:
            metadata: Extracted APK metadata

        Returns:
            ValidationResult
        """
        # ABI validation
        result = validate_abi(metadata, self.abi_policy)
        if not result.is_valid:
            self.validation_errors.append(result.error_message)
            return result
        if result.warning_message:
            self.validation_warnings.append(result.warning_message)

        # Package ID validation
        result = validate_package_id(metadata, self.allowed_ids)
        if not result.is_valid:
            self.validation_errors.append(result.error_message)
            return result

        # Signature validation
        result = validate_signature(
            metadata,
            self.cached_cert,
            self.allow_signature_change,
        )
        if not result.is_valid:
            self.validation_errors.append(result.error_message)
            return result
        if result.warning_message:
            self.validation_warnings.append(result.warning_message)

        # Version code validation
        version_code = metadata.get("version_code")
        if version_code is not None:
            result = validate_version_code(
                version_code,
                self.cached_highest_version,
            )
            if not result.is_valid:
                self.validation_errors.append(result.error_message)
                return result

            result = validate_duplicate_version_code(
                version_code,
                self.seen_version_codes,
            )
            if not result.is_valid:
                self.validation_errors.append(result.error_message)
                return result

            self.seen_version_codes.add(version_code)

        return ValidationResult(is_valid=True)


class GlobalValidator:
    """
    Global validator for cross-app validation.

    Tracks package IDs across all apps to detect duplicates.
    """

    def __init__(self):
        self.package_id_map: dict[str, str] = {}  # package_id -> logical_id
        self.duplicate_pairs: list[tuple[str, str, str]] = []  # (pkg_id, logical_id1, logical_id2)

    def register_package_id(
        self,
        package_id: str,
        logical_id: str,
    ) -> ValidationResult:
        """
        Register a package ID for a logical app.

        Args:
            package_id: Package ID to register
            logical_id: Logical app ID

        Returns:
            ValidationResult
        """
        result = validate_duplicate_package_id(
            package_id,
            self.package_id_map,
            logical_id,
        )

        if not result.is_valid:
            self.duplicate_pairs.append((package_id, self.package_id_map[package_id], logical_id))
            return result

        self.package_id_map[package_id] = logical_id
        return ValidationResult(is_valid=True)

    def get_duplicate_apps(self) -> list[tuple[str, str, str]]:
        """Get list of duplicate package ID pairs."""
        return self.duplicate_pairs
