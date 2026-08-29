"""Define the package-specific Analytics exception."""

from collections.abc import Mapping


class PparError(Exception):
    """Represent a ppar validation or calculation failure.

    Attributes:
        context: Independent machine-readable diagnostic context.
    """

    def __init__(
        self,
        message: str,
        *,
        context: Mapping[str, object] | None = None,
    ) -> None:
        """Initialize an actionable package error.

        Args:
            message: Human-readable failure description.
            context: Optional machine-readable diagnostic values.
        """
        self.context = dict(context or {})
        super().__init__(message)


__all__ = ["PparError"]
