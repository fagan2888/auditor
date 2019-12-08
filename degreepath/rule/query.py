import attr
from typing import Dict, List, Optional, Sequence, Iterator, Callable, Collection, Union, Tuple, cast, TYPE_CHECKING
import itertools
import logging
import decimal

from ..base import Rule, BaseQueryRule
from ..base.query import QuerySource
from ..limit import LimitSet
from ..clause import Clause, SingleClause, OrClause, AndClause, ClauseMode
from ..load_clause import load_clause
from ..data.clausable import Clausable
from ..solution.query import QuerySolution
from ..constants import Constants
from ..operator import Operator
from ..data import CourseInstance
from .assertion import AssertionRule, ConditionalAssertionRule, BaseAssertionRule

if TYPE_CHECKING:  # pragma: no cover
    from ..context import RequirementContext

logger = logging.getLogger(__name__)


@attr.s(cache_hash=True, slots=True, kw_only=True, frozen=True, auto_attribs=True)
class QueryRule(Rule, BaseQueryRule):
    load_potentials: bool

    @staticmethod
    def can_load(data: Dict) -> bool:
        if "from" in data:
            return True
        return False

    @staticmethod
    def load(data: Dict, *, c: Constants, path: List[str], ctx: Optional['RequirementContext'] = None) -> 'QueryRule':
        path = [*path, f".query"]

        source = QuerySource(data['from'])

        clause_mode = ClauseMode.Other
        if source is QuerySource.Courses:
            clause_mode = ClauseMode.Course
        elif source is QuerySource.Areas:
            clause_mode = ClauseMode.Area

        where = data.get("where", None)
        if where is not None:
            where = load_clause(where, c=c, ctx=ctx, mode=clause_mode)

        limit = LimitSet.load(data=data.get("limit", None), c=c)

        if 'limits' in data:
            raise ValueError(f'the key is "limit", not "limits": {data}')

        assertions: List[Union[AssertionRule, ConditionalAssertionRule]]
        if "assert" in data:
            assertions = [AssertionRule.load({'assert': data["assert"]}, c=c, path=[*path, ".assertions", "[0]"], mode=clause_mode)]
        elif "all" in data:
            assertions = [ConditionalAssertionRule.load(d, c=c, path=[*path, ".assertions", f"[{i}]"], mode=clause_mode) for i, d in enumerate(data["all"])]
        else:
            raise ValueError(f'you must have either an assert: or an all: key in {data}')

        if 'assert' in data and 'all' in data:
            raise ValueError(f'you cannot have both assert: and all: keys; {data}')

        allowed_keys = {'where', 'limit', 'claim', 'assert', 'all', 'allow_claimed', 'from', 'load_potentials'}
        given_keys = set(data.keys())
        assert given_keys.difference(allowed_keys) == set(), f"expected set {given_keys.difference(allowed_keys)} to be empty (at {path})"

        return QueryRule(
            source=source,
            assertions=tuple(assertions),
            limit=limit,
            where=where,
            allow_claimed=data.get('allow_claimed', False),
            attempt_claims=data.get('claim', True),
            load_potentials=data.get('load_potentials', True),
            path=tuple(path),
            inserted=tuple(),
        )

    def validate(self, *, ctx: 'RequirementContext') -> None:
        if self.assertions:
            for a in self.assertions:
                a.validate(ctx=ctx)

    def get_requirement_names(self) -> List[str]:
        return []

    def get_data(self, *, ctx: 'RequirementContext') -> Sequence[Clausable]:
        if self.source is QuerySource.Courses:
            return ctx.transcript()

        elif self.source is QuerySource.Areas:
            return list(ctx.areas)

        elif self.source is QuerySource.MusicPerformances:
            return list(ctx.music_performances)

        elif self.source is QuerySource.MusicAttendances:
            return list(ctx.music_attendances)

        else:
            raise TypeError(f'unknown type of data for query, {self.source}')

    def solutions(self, *, ctx: 'RequirementContext', depth: Optional[int] = None) -> Iterator[QuerySolution]:  # noqa: C901
        if ctx.get_waive_exception(self.path):
            logger.debug("forced override on %s", self.path)
            yield QuerySolution.from_rule(rule=self, output=tuple(), overridden=True)
            return

        data = self.get_data(ctx=ctx)
        assert len(self.assertions) > 0

        if self.where is not None:
            logger.debug("%s clause: %s", self.path, self.where)
            logger.debug("%s before filter: %s item(s)", self.path, len(data))

            data = [item for item in data if self.where.apply(item)]

            logger.debug("%s after filter: %s item(s)", self.path, len(data))

        did_iter = False
        for item_set in self.limit.limited_transcripts(data):
            if self.attempt_claims is False:
                did_iter = True

                # If we want to make things go green sooner, turn this on
                if self.source is QuerySource.Courses:
                    only_completed = tuple(c for c in item_set if isinstance(c, CourseInstance) and c.is_completed)
                    yield QuerySolution.from_rule(rule=self, output=only_completed)

                    only_current = tuple(c for c in item_set if isinstance(c, CourseInstance) and c.is_current)
                    yield QuerySolution.from_rule(rule=self, output=only_current)

                yield QuerySolution.from_rule(rule=self, output=item_set)
                continue

            for combo in iterate_item_set(item_set, rule=self):
                did_iter = True
                yield QuerySolution.from_rule(output=combo, rule=self)

        if not did_iter:
            # be sure we always yield something
            logger.debug("%s did not yield anything; yielding empty collection", self.path)
            yield QuerySolution.from_rule(rule=self, output=tuple())

    def has_potential(self, *, ctx: 'RequirementContext') -> bool:
        if self._has_potential(ctx=ctx):
            logger.debug('%s has potential: yes', self.path)
            return True
        else:
            logger.debug('%s has potential: no', self.path)
            return False

    def _has_potential(self, *, ctx: 'RequirementContext') -> bool:
        if ctx.has_exception(self.path):
            return True

        if has_assertion(self.assertions, key=get_lt_clauses):
            return True

        if has_assertion(self.assertions, key=get_at_least_0_clauses):
            return True

        if self.where is None:
            return len(self.get_data(ctx=ctx)) > 0

        return any(self.where.apply(item) for item in self.get_data(ctx=ctx))

    def all_matches(self, *, ctx: 'RequirementContext') -> Collection['Clausable']:
        matches = list(self.get_data(ctx=ctx))

        if self.where is not None:
            matches = [item for item in matches if self.where.apply(item)]

        for insert in ctx.get_insert_exceptions(self.path):
            matches.append(ctx.forced_course_by_clbid(insert.clbid, path=self.path))

        return matches

    def is_always_disjoint(self) -> bool:
        return self.allow_claimed is True and self.attempt_claims is False


def has_assertion(assertions: Sequence[Union[AssertionRule, ConditionalAssertionRule]], key: Callable[[SingleClause], Iterator[Clause]]) -> bool:
    if not assertions:
        return False

    for assertion in assertions:
        if isinstance(assertion, ConditionalAssertionRule):
            if check_assertion(assertion.when_yes, key) or check_assertion(assertion.when_no, key):
                return True

        elif check_assertion(assertion, key):
            return True

    return False


def check_assertion(assertion: Optional[AssertionRule], key: Callable[[SingleClause], Iterator[Clause]]) -> Optional[bool]:
    if not assertion:
        return None
    if assertion.where is not None:
        return None
    if has_clause(assertion.assertion, key=key):
        return True
    return None


def has_clause(clause: Clause, key: Callable[[SingleClause], Iterator[Clause]]) -> bool:
    if isinstance(clause, SingleClause):
        try:
            next(key(clause))
            return True
        except StopIteration:
            return False
    elif isinstance(clause, OrClause) or isinstance(clause, AndClause):
        return any(has_clause(c, key) for c in clause.children)


def get_clause_by(clause: Clause, key: Callable[[SingleClause], bool]) -> Iterator[SingleClause]:
    if isinstance(clause, SingleClause) and key(clause):
        yield clause
    elif isinstance(clause, OrClause) or isinstance(clause, AndClause):
        for c in clause.children:
            yield from get_clause_by(c, key)


def get_simple_count_clauses(clause: Clause) -> Iterator[SingleClause]:
    yield from get_clause_by(clause, lambda c: c.key in ('count(courses)', 'count(terms)'))


def get_simple_sum_clauses(clause: Clause) -> Iterator[SingleClause]:
    yield from get_clause_by(clause, lambda c: c.key in ('sum(credits)',))


def get_lt_clauses(clause: Clause) -> Iterator[SingleClause]:
    yield from get_clause_by(clause, lambda c: c.operator in (Operator.LessThan, Operator.LessThanOrEqualTo))


def get_at_least_0_clauses(clause: Clause) -> Iterator[SingleClause]:
    yield from get_clause_by(clause, lambda c: c.operator is Operator.GreaterThanOrEqualTo and c.expected == 0)


def get_largest_simple_count_assertion(assertions: Sequence[BaseAssertionRule]) -> Optional[SingleClause]:
    if not assertions:
        return None

    largest_clause = None
    largest_count = -1
    for assertion in assertions:
        clauses = get_simple_count_clauses(assertion.assertion)
        for clause in clauses:
            if type(clause.expected) == int and clause.expected > largest_count:
                largest_clause = clause
                largest_count = clause.expected

    return largest_clause


def get_largest_simple_sum_assertion(assertions: Sequence[BaseAssertionRule]) -> Optional[SingleClause]:
    if not assertions:
        return None

    largest_clause = None
    largest_expected = -1
    for assertion in assertions:
        clauses = get_simple_sum_clauses(assertion.assertion)
        for clause in clauses:
            if type(clause.expected) in (int, float, decimal.Decimal) and clause.expected > largest_expected:
                largest_clause = clause
                largest_expected = clause.expected

    return largest_clause


def iterate_item_set(item_set: Collection[Clausable], *, rule: QueryRule) -> Iterator[Tuple[Clausable, ...]]:
    assertions = []

    for a in rule.all_assertions():
        if isinstance(a, BaseAssertionRule):
            assertions.append(a)
        else:
            assertions.append(a.when_yes)
            if a.when_no:
                assertions.append(a.when_no)

    if rule.source is QuerySource.Courses:
        simple_count_assertion = get_largest_simple_count_assertion(assertions)
        if simple_count_assertion is not None:
            logger.debug("%s using simple assertion mode with %s", rule.path, simple_count_assertion)
            for n in simple_count_assertion.input_size_range(maximum=len(item_set)):
                yield from itertools.combinations(item_set, n)
            return

        simple_sum_assertion = get_largest_simple_sum_assertion(assertions)
        if simple_sum_assertion is not None:
            logger.debug("%s using simple-sum assertion mode with %s", rule.path, simple_sum_assertion)
            item_set_courses = cast(Sequence[CourseInstance], item_set)

            if sum(c.credits for c in item_set_courses) < simple_sum_assertion.expected:
                return

            for n in range(1, len(item_set_courses) + 1):
                for combo in itertools.combinations(item_set_courses, n):
                    if sum(c.credits for c in combo) >= simple_sum_assertion.expected:
                        yield combo
            return

        logger.debug("%s not running single assertion mode", rule.path)
        for n in range(1, len(item_set) + 1):
            yield from itertools.combinations(item_set, n)

    else:
        yield tuple(item_set)
