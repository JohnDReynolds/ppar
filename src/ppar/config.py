"""Load and validate the single ppar workspace configuration."""

from __future__ import annotations

from dataclasses import dataclass
import datetime as dt
import math
from pathlib import Path
from typing import Any, Final, Mapping, cast

import yaml

from ppar.errors import PparError
from ppar.frequency import Frequency
import ppar.utilities as util

_CONFIG_NAME: Final = "ppar.yaml"
_SOURCES: Final = frozenset({"axys_apx", "generic"})
_SETTING_KEYS: Final = frozenset(
    {
        "portfolio",
        "benchmark",
        "frequency",
        "holidays",
        "from_date",
        "thru_date",
        "classification",
        "annual_minimum_acceptable_return",
        "annual_risk_free_rate",
        "confidence_level",
        "portfolio_value",
        "currency_symbol",
    }
)
_ROOT_KEYS: Final = _SETTING_KEYS | {
    "source",
    "files",
    "mappings",
    "classifications",
    "security_id",
}


@dataclass(frozen=True)
class Settings:
    """Resolved settings for one workspace run.

    Attributes:
        workspace: Absolute workspace directory.
        config_path: Canonical ``ppar.yaml`` path.
        source: Explicit ``axys_apx`` or ``generic`` source selection.
        values: Parsed configuration passed to the selected source loader.
        portfolio: Axys/APX portfolio code, when applicable.
        benchmark: Axys/APX benchmark code, when applicable.
        frequency: Output reporting frequency.
        holidays: Optional headerless holiday file.
        from_date: Optional inclusive first date.
        thru_date: Optional inclusive last date.
        classification: Primary attribution classification.
        annual_minimum_acceptable_return: Annual downside-risk target.
        annual_risk_free_rate: Annual risk-free assumption.
        confidence_level: Value-at-risk confidence level.
        portfolio_value: Monetary basis for value at risk.
        currency_symbol: Currency marker for value at risk.
    """

    workspace: Path
    config_path: Path
    source: str
    values: Mapping[str, object]
    portfolio: str | None
    benchmark: str | None
    frequency: Frequency
    holidays: Path | None
    from_date: dt.date | None
    thru_date: dt.date | None
    classification: str
    annual_minimum_acceptable_return: float
    annual_risk_free_rate: float
    confidence_level: float
    portfolio_value: float
    currency_symbol: str


def load_config(workspace: util.PathLike = ".") -> dict[str, object]:
    """Load the canonical YAML mapping for a workspace.

    Args:
        workspace: Directory containing exactly one canonical ``ppar.yaml``.

    Returns:
        Parsed root mapping.

    Raises:
        PparError: If the file is missing, invalid YAML, or not a mapping.
    """
    config_path = Path(workspace).expanduser().resolve() / _CONFIG_NAME
    if not config_path.is_file():
        raise PparError(f"Configuration does not exist: {config_path}")
    try:
        loaded: Any = yaml.safe_load(config_path.read_text(encoding=util.ENCODING))
    except yaml.YAMLError as error:
        raise PparError(f"Invalid YAML in {config_path}: {error}") from error
    if not isinstance(loaded, dict):
        raise PparError(f"Configuration must be a YAML mapping: {config_path}")
    return cast(dict[str, object], loaded)


def settings(workspace: util.PathLike = ".") -> Settings:
    """Load and resolve one workspace through the canonical configuration path.

    Args:
        workspace: Directory containing ``ppar.yaml``.

    Returns:
        Immutable validated settings.

    Raises:
        PparError: If a required setting is missing or invalid.
    """
    workspace_path = Path(workspace).expanduser().resolve()
    values = load_config(workspace_path)
    source = values.get("source")
    if not isinstance(source, str) or source not in _SOURCES:
        raise PparError("source must be 'axys_apx' or 'generic'.")
    unsupported = sorted(str(key) for key in values if key not in _ROOT_KEYS)
    if unsupported:
        raise PparError(
            "Configuration has unsupported keys: " + ", ".join(unsupported) + ".",
        )

    portfolio = _optional_string(values.get("portfolio"), "portfolio")
    benchmark = _optional_string(values.get("benchmark"), "benchmark")
    if source == "axys_apx" and (portfolio is None or benchmark is None):
        raise PparError("portfolio and benchmark are required for Axys/APX.")
    confidence_level = _number(
        values.get("confidence_level", util.DEFAULT_CONFIDENCE_LEVEL),
        "confidence_level",
    )
    portfolio_value = _number(
        values.get("portfolio_value", util.DEFAULT_PORTFOLIO_VALUE),
        "portfolio_value",
    )
    if not 0.0 < confidence_level < 1.0:
        raise PparError("confidence_level must be between 0 and 1.")
    if portfolio_value <= 0.0:
        raise PparError("portfolio_value must be greater than zero.")

    return Settings(
        workspace=workspace_path,
        config_path=workspace_path / _CONFIG_NAME,
        source=source,
        values=values,
        portfolio=portfolio,
        benchmark=benchmark,
        frequency=_frequency(values.get("frequency")),
        holidays=_optional_path(workspace_path, values.get("holidays")),
        from_date=_optional_date(values.get("from_date"), "from_date"),
        thru_date=_optional_date(values.get("thru_date"), "thru_date"),
        classification=_string(
            values.get("classification", "Security"),
            "classification",
        ),
        annual_minimum_acceptable_return=_number(
            values.get(
                "annual_minimum_acceptable_return",
                util.DEFAULT_ANNUAL_MINIMUM_ACCEPTABLE_RETURN,
            ),
            "annual_minimum_acceptable_return",
        ),
        annual_risk_free_rate=_number(
            values.get("annual_risk_free_rate", util.DEFAULT_ANNUAL_RISK_FREE_RATE),
            "annual_risk_free_rate",
        ),
        confidence_level=confidence_level,
        portfolio_value=portfolio_value,
        currency_symbol=_string(
            values.get("currency_symbol", util.DEFAULT_CURRENCY_SYMBOL),
            "currency_symbol",
        ),
    )


def _string(value: object, name: str) -> str:
    """Return a required nonempty configuration string."""
    if not isinstance(value, str) or not value.strip():
        raise PparError(f"{name} must be a nonempty string.")
    return value


def _optional_string(value: object, name: str) -> str | None:
    """Return an optional nonempty configuration string."""
    if value is None:
        return None
    return _string(value, name)


def _number(value: object, name: str) -> float:
    """Return a finite numeric configuration value."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PparError(f"{name} must be numeric.")
    number = float(value)
    if not math.isfinite(number):
        raise PparError(f"{name} must be finite.")
    return number


def _optional_date(value: object, name: str) -> dt.date | None:
    """Return an optional ISO date."""
    if value is None:
        return None
    try:
        return util.convert_to_date(cast(Any, value))
    except (TypeError, ValueError, PparError) as error:
        raise PparError(f"{name} must be an ISO date.") from error


def _optional_path(workspace: Path, value: object) -> Path | None:
    """Return an optional workspace-relative path."""
    if value is None:
        return None
    path = Path(_string(value, "holidays")).expanduser()
    return path if path.is_absolute() else workspace / path


def _frequency(value: object) -> Frequency:
    """Return the configured reporting frequency."""
    if value is None:
        return Frequency.AS_OFTEN_AS_POSSIBLE
    normalized = _string(value, "frequency").casefold()
    frequencies = {
        "monthly": Frequency.MONTHLY,
        "quarterly": Frequency.QUARTERLY,
        "yearly": Frequency.YEARLY,
    }
    try:
        return frequencies[normalized]
    except KeyError as error:
        raise PparError(
            "frequency must be monthly, quarterly, or yearly.",
        ) from error
