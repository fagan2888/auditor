import abc
from typing import Iterator, Dict, Set, Any, List, Tuple, Collection, Optional, Union, TYPE_CHECKING
from decimal import Decimal
import enum
import attr
from functools import cmp_to_key, lru_cache
from ..status import ResultStatus

if TYPE_CHECKING:  # pragma: no cover
    from ..context import RequirementContext
    from ..claim import ClaimAttempt  # noqa: F401
    from ..data import CourseInstance  # noqa: F401
    from ..data import Clausable  # noqa: F401

Summable = Union[int, Decimal]


@enum.unique
class RuleState(enum.Enum):
    Rule = "rule"
    Solution = "solution"
    Result = "result"


@attr.s(cache_hash=True, slots=True, kw_only=True, frozen=True, auto_attribs=True)
class Base(abc.ABC):
    path: Tuple[str, ...]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": list(self.path),
            "type": self.type(),
            "status": self.status().value,
            "ok": self.ok(),
            "rank": str(self.rank()),
            "max_rank": str(self.max_rank()),
            "overridden": self.was_overridden(),
        }

    @abc.abstractmethod
    def type(self) -> str:
        raise NotImplementedError(f'must define a type() method')

    def state(self) -> RuleState:
        return RuleState.Rule

    def status(self) -> ResultStatus:
        if self.ok():
            return ResultStatus.Pass

        if self.complete_after_current_term():
            return ResultStatus.PendingCurrent

        if self.complete_after_registered():
            return ResultStatus.PendingRegistered

        if self.partially_complete():
            return ResultStatus.Partial

        return ResultStatus.NotStarted

    def ok(self) -> bool:
        if self.was_overridden():
            return True

        return False

    def partially_complete(self) -> bool:
        return 0 < self.rank() < self.max_rank()

    def complete_after_registered(self) -> bool:
        return self.partially_complete()

    def complete_after_current_term(self) -> bool:
        return self.complete_after_registered()

    def rank(self) -> Summable:
        return 0

    def max_rank(self) -> Summable:
        if self.ok():
            return self.rank()
        return 1

    def claims(self) -> List['ClaimAttempt']:
        return []

    def claims_for_gpa(self) -> List['ClaimAttempt']:
        return self.claims()

    def matched(self) -> Set['CourseInstance']:
        return set(claim.get_course() for claim in self.claims() if claim.failed is False)

    def matched_for_gpa(self) -> Set['CourseInstance']:
        return set(claim.get_course() for claim in self.claims_for_gpa() if claim.failed is False)

    def is_in_gpa(self) -> bool:
        return True

    def was_overridden(self) -> bool:
        return False

    def is_always_disjoint(self) -> bool:
        return False


class Result(Base, abc.ABC):
    __slots__ = ()

    def state(self) -> RuleState:
        return RuleState.Result


class Solution(Base):
    __slots__ = ()

    def state(self) -> RuleState:
        return RuleState.Solution

    @abc.abstractmethod
    def audit(self, *, ctx: 'RequirementContext') -> Result:
        raise NotImplementedError(f'must define an audit() method')


class Rule(Base):
    __slots__ = ()

    def state(self) -> RuleState:
        return RuleState.Rule

    @abc.abstractmethod
    def validate(self, *, ctx: 'RequirementContext') -> None:
        raise NotImplementedError(f'must define a validate() method')

    @abc.abstractmethod
    def get_requirement_names(self) -> List[str]:
        raise NotImplementedError(f'must define a get_requirement_names() method')

    @abc.abstractmethod
    def solutions(self, *, ctx: 'RequirementContext', depth: Optional[int] = None) -> Iterator[Solution]:
        raise NotImplementedError(f'must define a solutions() method')

    @abc.abstractmethod
    def has_potential(self, *, ctx: 'RequirementContext') -> bool:
        raise NotImplementedError(f'must define a has_potential() method')

    @abc.abstractmethod
    def all_matches(self, *, ctx: 'RequirementContext') -> Collection['Clausable']:
        raise NotImplementedError(f'must define an all_matches() method')


def compare_path_tuples(a: Base, b: Base) -> int:
    if a.path == b.path:
        # a equals b
        return 0
    elif compare_path_tuples__lt(a.path, b.path):
        # a is less-than b
        return -1
    else:
        # a is greater than b
        return 1


sort_by_path = cmp_to_key(compare_path_tuples)


@lru_cache(2048)
def compare_path_tuples__lt(a: Tuple[str, ...], b: Tuple[str, ...]) -> bool:
    """
    >>> compare_path_tuples__lt(('$', '.count', '[2]'), ('$', '.count', '[10]'))
    True
    >>> compare_path_tuples__lt(('$', '.count'), ('$', '[10]'))
    False
    >>> compare_path_tuples__lt(('$', '[10]'), ('$', '.count'))
    True
    >>> compare_path_tuples__lt(('$', '.count', '[2]'), ('$', '.count'))
    False
    >>> compare_path_tuples__lt(('$', '.count', '[2]'), ('$', '.count', '[3]', '.count', '[1]'))
    True
    """
    a_len = len(a)
    b_len = len(b)

    if a_len < b_len:
        return True

    if b_len < a_len:
        return False

    _1: Any
    _2: Any
    for _1, _2 in zip(a, b):
        # convert indices to integers
        if _1 and _1[0] == '[':
            _1 = int(_1[1:-1])

        if _2 and _2[0] == '[':
            _2 = int(_2[1:-1])

        if type(_1) == type(_2):
            if _1 == _2:
                continue
            if _1 < _2:
                return True
            else:
                return False
        elif type(_1) == int:
            return True
        else:
            return False

    return True
