import attr
from typing import Tuple, Union, TYPE_CHECKING
import logging

from ..base import Solution, BaseCountRule, Rule, Result
from ..result.count import CountResult
from ..result.assertion import AssertionResult

if TYPE_CHECKING:  # pragma: no cover
    from ..context import RequirementContext

logger = logging.getLogger(__name__)


@attr.s(cache_hash=True, slots=True, kw_only=True, frozen=True, auto_attribs=True)
class CountSolution(Solution, BaseCountRule):
    overridden: bool

    @staticmethod
    def from_rule(*, rule: BaseCountRule, count: int, items: Tuple[Union[Rule, Solution, Result], ...], overridden: bool = False) -> 'CountSolution':
        return CountSolution(
            count=count,
            items=items,
            audit_clauses=rule.audit_clauses,
            at_most=rule.at_most,
            path=rule.path,
            overridden=overridden,
        )

    def audit(self, *, ctx: 'RequirementContext') -> CountResult:
        if self.overridden:
            return CountResult.from_solution(
                solution=self,
                items=tuple(self.items),
                audit_results=tuple(self.audit_clauses),
                overridden=self.overridden,
            )

        results = tuple(r.audit(ctx=ctx) if isinstance(r, Solution) else r for r in self.items)
        initial_matched_items = tuple(item for sol in results for item in sol.matched())

        audit_results = []
        for clause in self.audit_clauses:
            exception = ctx.get_waive_exception(clause.path)
            if exception:
                logger.debug("forced override on %s", self.path)
                audit_results.append(AssertionResult(
                    where=clause.where,
                    assertion=clause.assertion,
                    path=clause.path,
                    message=clause.message,
                    overridden=True,
                    inserted=tuple(),
                ))
                continue

            override_value = ctx.get_value_exception(clause.path)
            if override_value:
                logger.debug("override: new value on %s", self.path)
                clause = clause.override_expected_value(override_value.value)

            if clause.where:
                matched_items = [item for item in initial_matched_items if clause.where.apply(item)]
            else:
                matched_items = [item for item in initial_matched_items]

            inserted_clbids = []
            for insert in ctx.get_insert_exceptions(clause.path):
                logger.debug("inserted %s into %s", insert.clbid, self.path)
                matched_course = ctx.forced_course_by_clbid(insert.clbid, path=self.path)
                matched_items.append(matched_course)
                inserted_clbids.append(matched_course.clbid)

            result = clause.assertion.compare_and_resolve_with(tuple(matched_items))

            audit_results.append(AssertionResult(
                where=clause.where,
                assertion=result,
                path=clause.path,
                message=clause.message,
                overridden=False,
                inserted=tuple(inserted_clbids),
            ))

        return CountResult.from_solution(
            solution=self,
            items=results,
            audit_results=tuple(audit_results),
        )
