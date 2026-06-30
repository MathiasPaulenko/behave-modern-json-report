"""Behave environment hooks — demonstrates attachment helpers and logging.

This file shows how to use the high-level attachment API from
behave-modern-json-report inside real Behave hooks.
"""
from __future__ import annotations

from behave_modern_json_report.attach import attach_text, attach_json, log


def before_all(context):
    log(context, "Test run starting", level="INFO")


def before_feature(context, feature):
    log(context, f"Starting feature: {feature.name}")


def before_scenario(context, scenario):
    log(context, f"Starting scenario: {scenario.name}")
    attach_json(context, {
        "feature": scenario.feature.name if hasattr(scenario, "feature") else None,
        "scenario": scenario.name,
        "tags": list(scenario.effective_tags) if hasattr(scenario, "effective_tags") else [],
    }, name="scenario-context.json")


def after_step(context, step):
    if step.status == "failed":
        attach_text(
            context,
            f"Step failed: {step.keyword} {step.name}\n"
            f"Error: {getattr(step, 'error_message', 'unknown')}",
            name="failure-details.txt",
        )
        log(context, f"Step failed: {step.keyword} {step.name}", level="ERROR")


def after_scenario(context, scenario):
    status = getattr(scenario, "status", "unknown")
    log(context, f"Scenario finished: {scenario.name} -> {status}")


def after_feature(context, feature):
    log(context, f"Feature finished: {feature.name}")


def after_all(context):
    log(context, "Test run complete", level="INFO")
