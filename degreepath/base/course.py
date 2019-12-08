import attr
from typing import Optional, Tuple, Dict, Any
from decimal import Decimal

from .bases import Base
from ..data.course_enums import GradeOption


@attr.s(cache_hash=True, slots=True, kw_only=True, frozen=True, auto_attribs=True)
class BaseCourseRule(Base):
    course: Optional[str] = None
    clbid: Optional[str] = None
    ap: Optional[str] = None
    institution: Optional[str] = None
    name: Optional[str] = None
    hidden: bool = False
    grade: Optional[Decimal] = None
    grade_option: Optional[GradeOption] = None
    allow_claimed: bool = False
    path: Tuple[str, ...] = tuple()
    inserted: bool = False
    overridden: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            **super().to_dict(),
            "course": self.course,
            "clbid": self.clbid,
            "hidden": self.hidden,
            "grade": str(self.grade) if self.grade is not None else None,
            "claims": [c.to_dict() for c in self.claims()],
            "ap": self.ap,
            "institution": self.institution,
            "name": self.name,
        }

    def type(self) -> str:
        return "course"

    def rank(self) -> Decimal:
        if self.partially_complete():
            return Decimal('0.5')

        if self.ok():
            return Decimal('1')

        return Decimal('0')

    def partially_complete(self) -> bool:
        return any(c.is_current or c.is_future_reg for c in self.matched()) or self.complete_after_registered()

    def complete_after_registered(self) -> bool:
        return any(c.is_future_reg for c in self.matched()) or self.complete_after_current_term()

    def complete_after_current_term(self) -> bool:
        return any(c.is_current for c in self.matched()) or self.ok()

    def max_rank(self) -> int:
        return 1

    def identifier(self) -> str:
        items = {'course': self.course, 'ap': self.ap, 'name': self.name, 'institution': self.institution}
        return ' '.join(f"{k}:{v}" for k, v in items.items())
