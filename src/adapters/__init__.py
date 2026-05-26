"""Court adapter registry — maps (state, county) → adapter class."""

from __future__ import annotations

from src.adapters.base_court import BaseCourt
from src.adapters.florida_hillsborough import FloridaHillsboroughAdapter
from src.adapters.florida_sarasota import FloridaSarasotaAdapter
from src.adapters.maryland_mjcs import MarylandMJCSAdapter


class CourtAdapterFactory:
    """
    Factory that returns the correct court adapter for a given state/county pair.

    Registry key: (state_code, county_name) — use ('MD', '*') as a wildcard
    that matches all Maryland counties using the same MJCS system.
    """

    REGISTRY: dict[tuple[str, str], type[BaseCourt]] = {
        ("MD", "*"):              MarylandMJCSAdapter,
        ("FL", "Sarasota"):       FloridaSarasotaAdapter,
        ("FL", "Hillsborough"):   FloridaHillsboroughAdapter,
    }

    @staticmethod
    def get(state: str, county: str) -> BaseCourt:
        """
        Return an instantiated court adapter for the given state and county.

        Args:
            state: Two-letter state code, e.g. 'MD'.
            county: County name matching the registry or states.json.

        Returns:
            Instantiated BaseCourt subclass.

        Raises:
            ValueError: If no adapter is registered for this state/county.
        """
        registry = CourtAdapterFactory.REGISTRY
        cls = registry.get((state, county)) or registry.get((state, "*"))
        if not cls:
            raise ValueError(
                f"No court adapter registered for {state}/{county}. "
                f"Register one in src/adapters/__init__.py"
            )
        return cls(county=county)


__all__ = ["CourtAdapterFactory", "BaseCourt"]
