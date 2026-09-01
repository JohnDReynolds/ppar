"""Write and transactionally publish portfolio analytics report bundles.

The context manager in this module lets applications write a full report bundle
to a staging sibling directory. A successful context replaces the entire public
output directory. Python exceptions and interruptions trigger cleanup and, when
publication has begun, restoration of the prior bundle.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from contextlib import contextmanager
import os
from pathlib import Path
import shutil
import tempfile
from typing import TYPE_CHECKING, TypeVar

from ppar.attribution import Chart, View
from ppar.errors import PparError
import ppar.utilities as util

if TYPE_CHECKING:
    from ppar.attribution import Attribution
    from ppar.risk import RiskStatistics

__all__ = ["atomic_output_directory", "write_report_bundle"]

_Selection = TypeVar("_Selection", View, Chart)


@contextmanager
def atomic_output_directory(output_directory: str | Path) -> Iterator[Path]:
    """Yield a staging directory and transactionally publish it on success.

    Args:
        output_directory: Directory that should contain the completed report
            bundle. Its parent is created when necessary.

    Yields:
        Empty staging directory in which the caller should write every file in
        the new report bundle.

    Raises:
        OSError: If the staging directory cannot be created or the completed
            bundle cannot be published. If publication fails, the prior output
            is restored whenever it existed.

    Notes:
        The complete ``output_directory`` is replaced; files from the prior
        directory are not retained. The transaction is rollback-safe for Python
        exceptions and interruptions, but it does not claim process-crash
        atomicity. Files must not be retained using the staging path because that
        path is renamed to ``output_directory`` on success.
    """
    output = Path(output_directory).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=f".{output.name}-staging-", dir=output.parent)
    )
    try:
        yield staging
        _publish(staging, output)
    except BaseException:  # pylint: disable=broad-exception-caught
        _remove(staging)
        raise


def write_report_bundle(
    *,
    output_directory: str | Path,
    security_attribution: Attribution | None = None,
    security_views: Iterable[View] = (),
    classification_attribution: Attribution | None = None,
    classification_views: Iterable[View] = (),
    classification_charts: Iterable[Chart] = (),
    risk_statistics: RiskStatistics | None = None,
) -> tuple[str, ...]:
    """Write a selected portfolio analytics report bundle.

    Args:
        output_directory: Directory receiving the report bundle.
        security_attribution: Attribution grouped by individual security.
            Required only when ``security_views`` contains a selection.
        security_views: Holding-level HTML tables to write. The default writes
            none.
        classification_attribution: Attribution grouped by another selected
            classification. Required only when a classification view or chart is
            selected.
        classification_views: Classification-level HTML tables to write. The
            default writes none.
        classification_charts: Classification-level PNG charts to write. The
            default writes none.
        risk_statistics: Completed risk-statistics calculation to write as an
            HTML table. The default writes no risk-statistics report.

    Returns:
        Output filenames in deterministic display order.

    Raises:
        PparError: If no reports are selected, a selection is repeated or has the
            wrong enum type, or a selected report category does not have its
            corresponding calculation.
        OSError: If the output directory or a report file cannot be written.

    Notes:
        Callers may write directly to their final output directory or use
        :func:`atomic_output_directory` for rollback-safe replacement of the
        complete bundle.
    """
    selected_security_views = _validated_selections(
        security_views,
        View,
        "security_views",
    )
    selected_classification_views = _validated_selections(
        classification_views,
        View,
        "classification_views",
    )
    selected_classification_charts = _validated_selections(
        classification_charts,
        Chart,
        "classification_charts",
    )

    if selected_security_views and security_attribution is None:
        raise PparError(
            "security_attribution is required when security_views are selected."
        )
    if (
        selected_classification_views or selected_classification_charts
    ) and classification_attribution is None:
        raise PparError(
            "classification_attribution is required when classification reports "
            "are selected."
        )
    if not (
        selected_security_views
        or selected_classification_views
        or selected_classification_charts
        or risk_statistics is not None
    ):
        raise PparError("At least one report must be selected.")

    output = Path(output_directory).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    report_names: list[str] = []

    # Holding-level views help trace a classification result back to the securities
    # that produced it.
    if security_attribution is not None:
        for view in selected_security_views:
            name = f"security_{view.name.lower()}.html"
            _write_text(output / name, security_attribution.to_html(view))
            report_names.append(name)

    # Enum names become predictable filenames such as
    # classification_overall_attribution.html.
    if classification_attribution is not None:
        for view in selected_classification_views:
            name = f"classification_{view.name.lower()}.html"
            _write_text(output / name, classification_attribution.to_html(view))
            report_names.append(name)

        # Charts use the same naming rule and are written as standalone PNG files.
        for chart in selected_classification_charts:
            name = f"classification_{chart.name.lower()}.png"
            (output / name).write_bytes(classification_attribution.to_chart(chart))
            report_names.append(name)

    if risk_statistics is not None:
        risk_name = "risk_statistics.html"
        _write_text(output / risk_name, risk_statistics.to_html())
        report_names.append(risk_name)

    return tuple(report_names)


def _publish(staging: Path, output: Path) -> None:
    """Replace ``output`` with ``staging`` while preserving rollback safety."""
    backup = Path(tempfile.mkdtemp(prefix=f".{output.name}-backup-", dir=output.parent))
    backup.rmdir()
    try:
        if output.exists():
            os.replace(output, backup)
        os.replace(staging, output)
    except BaseException:  # pylint: disable=broad-exception-caught
        if backup.exists():
            _remove(output)
            os.replace(backup, output)
        raise
    _remove(backup)


def _validated_selections(
    values: Iterable[_Selection],
    expected_type: type[_Selection],
    parameter: str,
) -> tuple[_Selection, ...]:
    """Return validated, unique report selections in caller-supplied order."""
    selections = tuple(values)
    seen: set[_Selection] = set()
    for index, selection in enumerate(selections):
        if not isinstance(selection, expected_type):
            raise PparError(
                f"{parameter}[{index}] must be a {expected_type.__name__}; received "
                f"{type(selection).__name__}.",
                context={
                    "parameter": parameter,
                    "index": index,
                    "expected_type": expected_type.__name__,
                    "actual_type": type(selection).__name__,
                },
            )
        if selection in seen:
            raise PparError(
                f"{parameter} contains repeated selection {selection.name}.",
                context={"parameter": parameter, "selection": selection.name},
            )
        seen.add(selection)
    return selections


def _remove(path: Path) -> None:
    """Remove a staging or backup path when it still exists."""
    if path.is_dir():
        shutil.rmtree(path, ignore_errors=True)
    elif path.exists():
        path.unlink(missing_ok=True)


def _write_text(path: Path, value: str) -> None:
    """Write one UTF-8 HTML report."""
    path.write_text(value, encoding=util.ENCODING)
