"""
Error reporting module.

Generates GitHub Actions annotations and summary reports
for build errors and warnings.
"""

import sys
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Severity(Enum):
    """Error severity levels."""

    ERROR = "error"
    WARNING = "warning"
    NOTICE = "notice"


@dataclass
class ReportEntry:
    """A single error or warning entry."""

    severity: Severity
    message: str
    logical_id: Optional[str] = None
    file: Optional[str] = None
    line: Optional[int] = None
    column: Optional[int] = None


class Reporter:
    """
    Reporter for GitHub Actions annotations.

    Collects errors and warnings, outputs GitHub Actions format,
    and generates summary reports.
    """

    def __init__(self):
        self.entries: list[ReportEntry] = []
        self.failed_apps: dict[str, list[str]] = {}  # logical_id -> list of errors
        self.warning_apps: dict[str, list[str]] = {}  # logical_id -> list of warnings

    def error(
        self,
        message: str,
        logical_id: Optional[str] = None,
        file: Optional[str] = None,
        line: Optional[int] = None,
    ) -> None:
        """
        Report an error.

        Args:
            message: Error message
            logical_id: App logical ID (optional)
            file: File path (optional)
            line: Line number (optional)
        """
        entry = ReportEntry(
            severity=Severity.ERROR,
            message=message,
            logical_id=logical_id,
            file=file,
            line=line,
        )
        self.entries.append(entry)

        # Track per-app errors
        if logical_id:
            if logical_id not in self.failed_apps:
                self.failed_apps[logical_id] = []
            self.failed_apps[logical_id].append(message)

        # Output GitHub Actions annotation
        self._print_annotation(entry)

    def warning(
        self,
        message: str,
        logical_id: Optional[str] = None,
        file: Optional[str] = None,
        line: Optional[int] = None,
    ) -> None:
        """
        Report a warning.

        Args:
            message: Warning message
            logical_id: App logical ID (optional)
            file: File path (optional)
            line: Line number (optional)
        """
        entry = ReportEntry(
            severity=Severity.WARNING,
            message=message,
            logical_id=logical_id,
            file=file,
            line=line,
        )
        self.entries.append(entry)

        # Track per-app warnings
        if logical_id:
            if logical_id not in self.warning_apps:
                self.warning_apps[logical_id] = []
            self.warning_apps[logical_id].append(message)

        # Output GitHub Actions annotation
        self._print_annotation(entry)

    def notice(
        self,
        message: str,
        logical_id: Optional[str] = None,
    ) -> None:
        """
        Report a notice (informational).

        Args:
            message: Notice message
            logical_id: App logical ID (optional)
        """
        entry = ReportEntry(
            severity=Severity.NOTICE,
            message=message,
            logical_id=logical_id,
        )
        self.entries.append(entry)
        self._print_annotation(entry)

    def _print_annotation(self, entry: ReportEntry) -> None:
        """Print GitHub Actions annotation to stdout."""
        # Build location prefix if file specified
        location_parts = []
        if entry.file:
            location_parts.append(f"file={entry.file}")
        if entry.line:
            location_parts.append(f"line={entry.line}")
        if entry.column:
            location_parts.append(f"col={entry.column}")

        location = ",".join(location_parts)
        if location:
            location = f" {location}"

        # Print annotation
        print(f"::{entry.severity.value}::{entry.message}", file=sys.stderr)

    def print_summary(self) -> None:
        """Print summary of all errors and warnings."""
        if not self.entries:
            print("\n## Summary", file=sys.stderr)
            print("No errors or warnings.", file=sys.stderr)
            return

        # Count by severity
        error_count = sum(1 for e in self.entries if e.severity == Severity.ERROR)
        warning_count = sum(1 for e in self.entries if e.severity == Severity.WARNING)

        print("\n## Summary", file=sys.stderr)
        print(f"Total: {error_count} errors, {warning_count} warnings", file=sys.stderr)

        # Print failed apps section
        if self.failed_apps:
            print("\n## Failed Apps", file=sys.stderr)
            for logical_id, errors in self.failed_apps.items():
                for error in errors:
                    print(f"- {logical_id}: {error}", file=sys.stderr)

        # Print warning apps section
        if self.warning_apps:
            print("\n## Warnings", file=sys.stderr)
            for logical_id, warnings in self.warning_apps.items():
                for warning in warnings:
                    print(f"- {logical_id}: {warning}", file=sys.stderr)

    def has_errors(self) -> bool:
        """Check if any errors were reported."""
        return any(e.severity == Severity.ERROR for e in self.entries)

    def has_failures(self) -> bool:
        """Check if any apps failed."""
        return len(self.failed_apps) > 0

    def get_failed_apps(self) -> dict[str, list[str]]:
        """Get dictionary of failed apps and their errors."""
        return self.failed_apps.copy()

    def get_error_count(self) -> int:
        """Get total error count."""
        return sum(1 for e in self.entries if e.severity == Severity.ERROR)

    def get_warning_count(self) -> int:
        """Get total warning count."""
        return sum(1 for e in self.entries if e.severity == Severity.WARNING)


def format_yaml_error(line: int, message: str) -> str:
    """Format error message for YAML file."""
    return f"apps.yaml:{line}: {message}"


def format_app_error(logical_id: str, message: str) -> str:
    """Format error message for app processing."""
    return f"{logical_id}: {message}"
