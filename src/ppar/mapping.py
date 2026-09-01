"""Provide mapping support between two classification schemes.

This module contains the ``Mapping`` class, which loads a two-column mapping
data source and creates a reverse lookup from each destination classification
item to the source classification items that map to it.
"""

# Python imports
from collections import defaultdict
from typing import Sequence

# Project Imports
import ppar.schema as cols
import ppar.utilities as util


class Mapping:
    """Map source classification items to destination classification items.

    A ``Mapping`` instance is typically used to roll up lower-level
    classification items, such as securities, into higher-level classification
    items, such as economic sectors.

    Attributes:
        to_froms: Reverse mapping whose keys are destination classification
            identifiers and whose values are lists of source classification
            identifiers that map to each destination identifier.
    """

    def __init__(
        self,
        from_items_to_map: Sequence[str],
        data_source: util.MappingDataSource,
    ):
        """Create a mapping from one classification to another.

        The mapping data source must contain two columns: the first column is
        the source classification identifier and the second column is the
        destination classification identifier. Source items that are not present
        in the mapping data source are mapped to themselves.

        Args:
            from_items_to_map: Source classification identifiers that must be
                mapped.
            data_source: Mapping data source. This can be a CSV file path or a
                Polars DataFrame.

        Data Parameters:
            Sample source-data rows for mapping a ``Security`` classification
            to an ``Economic Sector`` classification::

                AAPL, IT
                GOOG, CO
                XOM,  EN

            The source classification identifier is in the first column and the
            destination classification identifier is in the second column. CSV
            input is expected to have no column headers.

        Raises:
            PparError: Raised by ``util.load_datasource()`` if ``data_source``
                does not exist when provided as a file path, or if the loaded
                mapping data does not contain exactly two columns or contains
                an invalid source or destination identity.
        """
        # Load the data source into dataframe with 2 columns: 0=from, 1=to
        from_tos = util.load_datasource(
            data_source,
            column_names=cols.FROM_TO_COLUMNS,
            needed_items=from_items_to_map,
            error_message="Mapping data must contain exactly two columns.",
            source_description="Mapping data",
            identity_column_indices=(0, 1),
        )

        # Turn the from_tos dataframe into a dictionary.
        mappings = dict(
            zip(
                from_tos[from_tos.columns[0]],
                from_tos[from_tos.columns[1]],
            )
        )

        # If from_item is not in mappings, then add it pointing to itself.
        mappings = {
            from_item: (from_item if from_item not in mappings else mappings[from_item])
            for from_item in from_items_to_map
        }

        # Create a reverse mapping from `to_column_name` to a list of `from_column_names`.
        self._to_froms: defaultdict[str, list[str]] = defaultdict(list)
        for from_value, to_value in mappings.items():
            self._to_froms[to_value].append(from_value)

    @property
    def to_froms(self) -> dict[str, list[str]]:
        """Return an independent reverse-mapping dictionary."""
        return {
            to_value: list(from_values)
            for to_value, from_values in self._to_froms.items()
        }
