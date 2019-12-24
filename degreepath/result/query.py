import attr
from typing import Tuple, Sequence, List, Union, Optional, TYPE_CHECKING

from .assertion import AssertionResult
from ..base import Result, BaseQueryRule, Summable, BaseAssertionRule
from ..claim import ClaimAttempt

if TYPE_CHECKING:  # pragma: no cover
    from ..base.query import QuerySource
    from ..limit import LimitSet
    from ..clause import Clause  # noqa: F401
    from ..rule.assertion import AssertionRule, ConditionalAssertionRule  # noqa: F401


@attr.s(cache_hash=True, slots=True, kw_only=True, frozen=True, auto_attribs=True)
class QueryResult(Result, BaseQueryRule):
    # TODO: try removing these annotations when MYPY > 0.761
    # these are copied from BaseQueryRule, because mypy doesn't seem to
    # understand … something … without them also being present here.
    allow_claimed: bool
    assertions: Tuple[Union['AssertionRule', 'ConditionalAssertionRule'], ...]
    attempt_claims: bool
    force_inserted: Tuple[str, ...]
    inserted: Tuple[str, ...]
    limit: 'LimitSet'
    path: Tuple[str, ...]
    source: 'QuerySource'
    where: Optional['Clause']

    successful_claims: Tuple[ClaimAttempt, ...]
    failed_claims: Tuple[ClaimAttempt, ...]
    resolved_assertions: Tuple[AssertionResult, ...]
    success: bool
    overridden: bool

    @staticmethod
    def from_solution(
        *,
        solution: BaseQueryRule,
        resolved_assertions: Tuple[AssertionResult, ...],
        successful_claims: Tuple[ClaimAttempt, ...],
        failed_claims: Tuple[ClaimAttempt, ...],
        success: bool,
        overridden: bool = False,
    ) -> 'QueryResult':
        return QueryResult(
            allow_claimed=solution.allow_claimed,
            assertions=solution.assertions,
            attempt_claims=solution.attempt_claims,
            failed_claims=failed_claims,
            force_inserted=solution.force_inserted,
            inserted=solution.inserted,
            limit=solution.limit,
            overridden=overridden,
            path=solution.path,
            resolved_assertions=resolved_assertions,
            source=solution.source,
            success=success,
            successful_claims=successful_claims,
            where=solution.where,
        )

    def only_failed_claims(self) -> Sequence[ClaimAttempt]:
        return self.failed_claims

    def all_assertions(self) -> Sequence[Union[BaseAssertionRule, 'ConditionalAssertionRule']]:
        return self.resolved_assertions

    def claims(self) -> List[ClaimAttempt]:
        return list(self.successful_claims)

    def was_overridden(self) -> bool:
        return self.overridden

    def ok(self) -> bool:
        if self.was_overridden():
            return True

        return self.success is True

    def rank(self) -> Summable:
        return sum(a.rank() for a in self.resolved_assertions)

    def max_rank(self) -> Summable:
        return sum(a.max_rank() for a in self.resolved_assertions)
