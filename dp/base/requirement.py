import attr
from typing import Optional, Dict, Any, List, TYPE_CHECKING
import enum

from .bases import Base, Summable

if TYPE_CHECKING:  # pragma: no cover
    from ..claim import ClaimAttempt  # noqa: F401


@enum.unique
class AuditedBy(enum.Enum):
    Department = "department"
    Registrar = "registrar"


@attr.s(cache_hash=True, slots=True, kw_only=True, frozen=True, auto_attribs=True)
class BaseRequirementRule(Base):
    name: str
    message: Optional[str]
    result: Optional[Base]
    audited_by: Optional[AuditedBy]
    is_contract: bool
    in_gpa: bool
    disjoint: Optional[bool]

    def to_dict(self) -> Dict[str, Any]:
        return {
            **super().to_dict(),
            "name": self.name,
            "message": self.message,
            "result": self.result.to_dict() if self.result is not None else None,
            "audited_by": self.audited_by.value if self.audited_by else None,
            "contract": self.is_contract,
        }

    def type(self) -> str:
        return "requirement"

    def rank(self) -> Summable:
        if self.audited_by is not None and self.ok():
            return 1

        if self.result is None:
            return 0

        boost = 1 if self.ok() else 0
        return self.result.rank() + boost

    def max_rank(self) -> Summable:
        if self.audited_by is not None and self.ok():
            return self.rank()

        if self.result is None:
            return 1

        if self.ok():
            return self.rank()

        return self.result.max_rank() + 1

    def in_progress(self) -> bool:
        if self.result is None:
            return super().in_progress()

        return self.result.in_progress()

    def is_always_disjoint(self) -> bool:
        if self.disjoint is True:
            return True

        if self.result is None:
            return super().is_always_disjoint()

        return self.result.is_always_disjoint()

    def is_never_disjoint(self) -> bool:
        if self.disjoint is False:
            return True

        if self.result is None:
            return super().is_never_disjoint()

        return self.result.is_never_disjoint()

    def is_in_gpa(self) -> bool:
        return self.in_gpa

    def claims(self) -> List['ClaimAttempt']:
        if self.audited_by or self.result is None:
            return []

        return self.result.claims()

    def claims_for_gpa(self) -> List['ClaimAttempt']:
        if self.is_in_gpa() and self.result is not None and not self.audited_by:
            return self.result.claims_for_gpa()

        return []
