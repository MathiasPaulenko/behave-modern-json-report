"""Validation — JSON Schema validation and runtime structural checks.

The JSON Schema validator is optional: it uses ``jsonschema`` when available
(the ``[validate]`` extra).  When ``jsonschema`` is not installed a built-in
structural validator provides equivalent coverage for the core schema.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from .models import ExecutionReport
from .schema import SCHEMA_FILE
from .serializer import Serializer


@dataclass(slots=True)
class ValidationError:
    """A single validation error."""

    path: str
    message: str

    def __str__(self) -> str:
        return f"{self.path}: {self.message}"


@dataclass(slots=True)
class ValidationResult:
    """Aggregated validation result."""

    valid: bool
    errors: list[ValidationError] = field(default_factory=list)

    def add(self, path: str, message: str) -> None:
        self.errors.append(ValidationError(path=path, message=message))
        self.valid = False

    def __bool__(self) -> bool:
        return self.valid


def load_schema() -> dict[str, Any]:
    """Load the bundled JSON Schema from disk."""
    with SCHEMA_FILE.open("r", encoding="utf-8") as fh:
        return dict(json.load(fh))


def _jsonschema_available() -> bool:
    try:
        import jsonschema  # type: ignore[import-untyped]  # noqa: F401

        return True
    except Exception:
        return False


def validate_dict(data: dict[str, Any]) -> ValidationResult:
    """Validate a JSON-ready dictionary against the execution schema."""
    result = ValidationResult(valid=True)

    if _jsonschema_available():
        try:
            import jsonschema

            schema = load_schema()
            validator_cls = jsonschema.Draft202012Validator
            validator = validator_cls(schema)
            for error in validator.iter_errors(data):
                path = ".".join(str(p) for p in error.absolute_path) or "<root>"
                result.add(path=path, message=error.message)
        except Exception as exc:  # pragma: no cover - defensive
            result.add(path="<schema>", message=f"schema validation crashed: {exc}")
        return result

    # Fallback structural validator.
    _structural_validate(data, result)
    return result


def validate_report(report: ExecutionReport) -> ValidationResult:
    """Serialize ``report`` and validate the resulting dictionary."""
    data = Serializer().to_dict(report)
    return validate_dict(data)


def validate_json(text: str) -> ValidationResult:
    """Parse and validate a JSON string."""
    result = ValidationResult(valid=True)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        result.add(path="<json>", message=f"invalid JSON: {exc}")
        return result
    if not isinstance(data, dict):
        result.add(path="<root>", message="root must be an object")
        return result
    return validate_dict(data)


# ---------------------------------------------------------------------------
# Built-in structural validator (used when jsonschema is unavailable)
# ---------------------------------------------------------------------------


def _structural_validate(data: Any, result: ValidationResult, path: str = "") -> None:
    if not isinstance(data, dict):
        result.add(path or "<root>", "expected an object")
        return

    _check_str(data, "schemaVersion", result, path, required=True)
    if isinstance(data.get("schemaVersion"), str):
        # Warn on major-version mismatch but do not hard-fail.
        pass

    _check_object(data, "execution", result, path, required=True)
    _check_object(data, "statistics", result, path, required=True)
    _check_object(data, "environment", result, path, required=False)
    _check_array(data, "features", result, path, required=True)
    _check_object(data, "metadata", result, path, required=True)

    exec_data = data.get("execution")
    if isinstance(exec_data, dict):
        ep = f"{path}.execution" if path else "execution"
        _check_str(exec_data, "executionId", result, ep, required=True)
        _check_str(exec_data, "status", result, ep, required=True)
        _check_number(exec_data, "duration", result, ep, required=True)

    stats_data = data.get("statistics")
    if isinstance(stats_data, dict):
        sp = f"{path}.statistics" if path else "statistics"
        for field_name in (
            "features",
            "scenarios",
            "steps",
            "passed",
            "failed",
            "skipped",
            "undefined",
            "pending",
        ):
            _check_int(stats_data, field_name, result, sp, required=True)
        _check_number(stats_data, "passRate", result, sp, required=True)
        _check_number(stats_data, "duration", result, sp, required=True)

    features = data.get("features")
    if isinstance(features, list):
        for i, feature in enumerate(features):
            fp = f"{path}.features[{i}]"
            if not isinstance(feature, dict):
                result.add(fp, "expected an object")
                continue
            _check_str(feature, "id", result, fp, required=True)
            _check_str(feature, "name", result, fp, required=True)
            _check_str(feature, "status", result, fp, required=True)
            _check_number(feature, "duration", result, fp, required=True)
            _check_array(feature, "scenarios", result, fp, required=True)

            scenarios = feature.get("scenarios")
            if isinstance(scenarios, list):
                for j, sc in enumerate(scenarios):
                    sp2 = f"{fp}.scenarios[{j}]"
                    if not isinstance(sc, dict):
                        result.add(sp2, "expected an object")
                        continue
                    _check_str(sc, "id", result, sp2, required=True)
                    _check_str(sc, "name", result, sp2, required=True)
                    _check_str(sc, "featureId", result, sp2, required=True)
                    _check_str(sc, "status", result, sp2, required=True)
                    _check_number(sc, "duration", result, sp2, required=True)
                    _check_array(sc, "steps", result, sp2, required=True)

                    steps = sc.get("steps")
                    if isinstance(steps, list):
                        for k, step in enumerate(steps):
                            stp = f"{sp2}.steps[{k}]"
                            if not isinstance(step, dict):
                                result.add(stp, "expected an object")
                                continue
                            _check_str(step, "id", result, stp, required=True)
                            _check_str(step, "keyword", result, stp, required=True)
                            _check_str(step, "text", result, stp, required=True)
                            _check_str(step, "status", result, stp, required=True)
                            _check_number(step, "duration", result, stp, required=True)


def _check_str(
    data: dict[str, Any],
    key: str,
    result: ValidationResult,
    path: str,
    *,
    required: bool,
) -> None:
    if key not in data:
        if required:
            result.add(f"{path}.{key}", "is required")
        return
    if not isinstance(data[key], str):
        result.add(f"{path}.{key}", f"expected string, got {type(data[key]).__name__}")


def _check_number(
    data: dict[str, Any],
    key: str,
    result: ValidationResult,
    path: str,
    *,
    required: bool,
) -> None:
    if key not in data:
        if required:
            result.add(f"{path}.{key}", "is required")
        return
    if not isinstance(data[key], (int, float)):
        result.add(f"{path}.{key}", f"expected number, got {type(data[key]).__name__}")


def _check_int(
    data: dict[str, Any],
    key: str,
    result: ValidationResult,
    path: str,
    *,
    required: bool,
) -> None:
    if key not in data:
        if required:
            result.add(f"{path}.{key}", "is required")
        return
    if not isinstance(data[key], int) or isinstance(data[key], bool):
        result.add(f"{path}.{key}", f"expected integer, got {type(data[key]).__name__}")


def _check_object(
    data: dict[str, Any],
    key: str,
    result: ValidationResult,
    path: str,
    *,
    required: bool,
) -> None:
    if key not in data:
        if required:
            result.add(f"{path}.{key}", "is required")
        return
    if not isinstance(data[key], dict):
        result.add(f"{path}.{key}", f"expected object, got {type(data[key]).__name__}")


def _check_array(
    data: dict[str, Any],
    key: str,
    result: ValidationResult,
    path: str,
    *,
    required: bool,
) -> None:
    if key not in data:
        if required:
            result.add(f"{path}.{key}", "is required")
        return
    if not isinstance(data[key], list):
        result.add(f"{path}.{key}", f"expected array, got {type(data[key]).__name__}")


__all__ = [
    "ValidationError",
    "ValidationResult",
    "load_schema",
    "validate_dict",
    "validate_json",
    "validate_report",
]
