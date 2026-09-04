"""Classification metadata used by attribution and reporting.

This module defines the ``Classification`` class, which stores the identifiers
and display names associated with a classification such as security, sector,
country, or another user-defined grouping.
"""

# Python Imports
from pathlib import Path
from typing import Sequence

# Third-Party Imports
import polars as pl

# Project Imports
from ppar._perfattr_adapter import normalize_classification_source
import ppar.schema as cols
from ppar.performance import Performance
import ppar.utilities as util

_EMPTY_DF = pl.DataFrame(
    schema={cols.CLASSIFICATION_IDENTIFIER: pl.String, cols.CLASSIFICATION_NAME: pl.String}
)


class Classification:
    """Store classification identifiers and names in a Polars DataFrame.

    A ``Classification`` instance contains a two-column DataFrame with
    classification identifiers and their corresponding display names. The data
    can come directly from a classification data source, or it can be inferred
    from the classification items already present on matching portfolio and
    benchmark ``Performance`` instances.

    Attributes:
        name: Classification name associated with the identifiers.
        df: Polars DataFrame containing ``classification_identifier`` and
            ``classification_name`` columns.
    """

    def __init__(
        self,
        name: str | None,
        data_source: str | Path | pl.DataFrame | None,
        performances: Sequence[Performance] | None = None,
    ):
        """Initialize a classification from a data source or performances.

        Args:
            name: Optional classification name to use when ``data_source`` is
                supplied.
            data_source: Classification data source supplied as a CSV path or
                Polars DataFrame. The
                data must contain exactly two columns: classification identifier
                and classification display name. If this value is omitted, the
                classification is inferred from ``performances``.
            performances: Optional sequence containing the portfolio Performance at
                index 0 and the benchmark Performance at index 1. Required when
                ``data_source`` is supplied because the data source is filtered
                to identifiers used by those performances. Also used as the
                fallback source when ``data_source`` is omitted.

        Data Parameters:
            Example classification data for an Economic Sector classification,
            with no column headers::

                CO, Communication Services
                EN, Energy
                IT, Information Technology

        Raises:
            PparError: Propagated from the portable adapter if ``data_source`` is a
                missing file path, malformed, or contains invalid or conflicting
                identities.
            TypeError: If ``data_source`` is supplied and ``performances`` is
                ``None``.
        """
        if performances is not None:
            performances = util.two_item_tuple(
                performances, "Classification performances"
            )

        # Get the 2-column dataframe [cols.CLASSIFICATION_IDENTIFIER, cols.CLASSIFICATION_NAME]
        if data_source is None:
            # Use the performances.classification_items.
            self.name, self._df = Classification._load_from_performances(performances)
        else:
            # Use the data_source.
            if performances is None:
                raise TypeError("performances is required when data_source is supplied.")
            self.name = name
            needed_items = list(
                set(performances[0].identifiers) | set(performances[1].identifiers)
            )  # unique list of the union of portfolio and benchmark
            normalized = normalize_classification_source(data_source)
            normalized = normalized.loc[
                normalized["classification_identifier"].isin(needed_items)
            ]
            self._df = pl.DataFrame(
                {
                    cols.CLASSIFICATION_IDENTIFIER: normalized[
                        "classification_identifier"
                    ].to_numpy(),
                    cols.CLASSIFICATION_NAME: normalized[
                        "classification_name"
                    ].to_numpy(),
                }
            )

    @property
    def df(self) -> pl.DataFrame:
        """Return an independent classification metadata table."""
        return self._df.clone()

    @staticmethod
    def _load_from_performances(
        performances: Sequence[Performance] | None,
    ) -> tuple[str | None, pl.DataFrame]:
        """Build classification metadata from portfolio and benchmark data.

        Uses the ``classification_items`` DataFrames already stored on the
        supplied portfolio and benchmark ``Performance`` instances. If both
        performances share the same classification name, their classification
        items are combined. Exact duplicate identifier/name pairs are collapsed;
        conflicting names are rejected.

        Args:
            performances: Sequence containing the portfolio Performance at index 0
                and the benchmark Performance at index 1. If omitted, or if the
                two performances do not have the same classification name, an
                empty classification is returned.

        Returns:
            Tuple containing the resolved classification name and a two-column
            Polars DataFrame of classification identifiers and names. Returns
            ``None`` and an empty typed DataFrame when no matching classification
            data is available.
        """
        # Return empty if there are no performances or the portfolio and benchmark do not share
        # the same classification name.
        if (not performances) or (
            performances[0].classification_name != performances[1].classification_name
        ):
            return None, _EMPTY_DF

        # Get the classification items from the portfolio and benchmark Performance objects.
        dfs = [
            performance.classification_items
            for performance in performances
            if not performance.classification_items.is_empty()
        ]

        # Return empty if the performances do not have any classification_items.
        if not dfs:
            return None, _EMPTY_DF

        # Concatenate the portfolio and benchmark classification items. Exact duplicate
        # pairs are harmless; different names for one identifier are ambiguous.
        normalized = normalize_classification_source(
            pl.concat(dfs, how="vertical")
        )
        df = pl.DataFrame(
            {
                cols.CLASSIFICATION_IDENTIFIER: normalized[
                    "classification_identifier"
                ].to_numpy(),
                cols.CLASSIFICATION_NAME: normalized["classification_name"].to_numpy(),
            }
        )

        # Return the classification name common to both streams and the combined items.
        return performances[0].classification_name, df
