"""Per-domain budget enforcement (Plan 16 Task 28 / D26 step 3 of 4).

The legacy global guard (`brain_core.cost.budget.BudgetEnforcer`) compares
projected spend against a single ``daily_usd`` / ``monthly_usd`` cap. This
package adds the per-domain layer: each domain may carry its own
:class:`brain_core.config.schema.BudgetOverride` cap that is checked
independently, BEFORE the LLM call, against rolling 24h / 30d windows.
"""

from brain_core.budget.per_domain_guard import (
    BudgetCapExceeded,
    PerDomainBudgetGuard,
)

__all__ = ["BudgetCapExceeded", "PerDomainBudgetGuard"]
