"""behave-modern-json-report — canonical JSON execution model for Behave.

Public API:
    serialize            -- serialize an ExecutionReport to JSON.
    validate_report      -- validate an ExecutionReport model.
    validate_dict        -- validate a JSON-ready dict.
    validate_json        -- parse and validate a JSON string.
    Serializer           -- configurable model-to-JSON serializer.
    SerializerOptions    -- configuration for the serializer.
    Collector            -- builds the model from Behave events.
    ModernJSONFormatter  -- Behave Formatter API entry point.
    attach_file          -- attach a file to the current step.
    attach_text          -- attach text to the current step.
    attach_json          -- attach JSON data to the current step.
    attach_screenshot    -- attach a screenshot to the current step.
    log                  -- append a log line to the current step.
"""

from __future__ import annotations

from .attach import attach_file, attach_json, attach_screenshot, attach_text, log
from .collector import Collector
from .cucumber_formatter import CucumberJSONFormatter
from .cucumber_serializer import (
    CucumberSerializer,
    CucumberSerializerOptions,
    serialize_cucumber,
)
from .formatter import ModernJSONFormatter
from .models import (
    Attachment,
    Background,
    DataTable,
    DataTableRow,
    DocString,
    Environment,
    Error,
    Execution,
    ExecutionReport,
    Feature,
    Location,
    Metadata,
    Scenario,
    Statistics,
    Step,
    StepLog,
)
from .schema import SCHEMA_VERSION
from .serializer import Serializer, SerializerOptions, serialize
from .validator import ValidationResult, validate_dict, validate_json, validate_report

__version__ = "1.1.0"

__all__ = [
    "SCHEMA_VERSION",
    "__version__",
    # models
    "Attachment",
    "Background",
    "DataTable",
    "DataTableRow",
    "DocString",
    "Environment",
    "Error",
    "Execution",
    "ExecutionReport",
    "Feature",
    "Location",
    "Metadata",
    "Scenario",
    "Statistics",
    "Step",
    "StepLog",
    # serializer
    "Serializer",
    "SerializerOptions",
    "serialize",
    # validator
    "ValidationResult",
    "validate_dict",
    "validate_json",
    "validate_report",
    # collector + formatters
    "Collector",
    "CucumberJSONFormatter",
    "CucumberSerializer",
    "CucumberSerializerOptions",
    "ModernJSONFormatter",
    "serialize_cucumber",
    # attach helpers
    "attach_file",
    "attach_json",
    "attach_screenshot",
    "attach_text",
    "log",
]
