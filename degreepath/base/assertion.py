import attr
from typing import Optional, Tuple, Dict, Any
from decimal import Decimal

from ..clause import Clause, SingleClause
from .bases import Base, Summable


@attr.s(cache_hash=True, slots=True, kw_only=True, frozen=True, auto_attribs=True)
class BaseAssertionRule(Base):
    assertion: SingleClause
    where: Optional[Clause]
    path: Tuple[str, ...]
    inserted: Tuple[str, ...]
    message: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            **super().to_dict(),
            "assertion": self.assertion.to_dict() if self.assertion else None,
            "where": self.where.to_dict() if self.where else None,
            "message": self.message,
            "inserted": list(self.inserted),
        }

    def type(self) -> str:
        return "assertion"

    def rank(self) -> Summable:
        return self.assertion.rank()

    def max_rank(self) -> Summable:
        if self.ok():
            return self.assertion.rank()

        return self.assertion.max_rank()

    def ok(self) -> bool:
        if self.was_overridden():
            return True

        return self.assertion.ok()

    def partially_complete(self) -> bool:
        return self.assertion.partially_complete()

    def complete_after_current_term(self) -> bool:
        return self.assertion.complete_after_current_term()

    def complete_after_registered(self) -> bool:
        return self.assertion.complete_after_registered()

    def override_expected_value(self, value: Decimal) -> 'BaseAssertionRule':
        clause = self.assertion.override_expected(value)

        return attr.evolve(self, assertion=clause)
