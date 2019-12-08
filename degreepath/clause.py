from collections.abc import Iterable
from typing import Union, List, Set, Tuple, Dict, Any, Mapping, Callable, Optional, Iterator, Sequence, cast, TYPE_CHECKING
import logging
from decimal import Decimal, InvalidOperation
import abc
import enum
import attr

from .constants import Constants
from .lib import str_to_grade_points
from .operator import Operator, apply_operator, str_operator
from .data.course_enums import GradeOption, GradeCode
from .status import ResultStatus
from .apply_clause import apply_clause_to_assertion_with_courses, apply_clause_to_assertion_with_areas, apply_clause_to_assertion_with_data
from functools import lru_cache

if TYPE_CHECKING:  # pragma: no cover
    from .context import RequirementContext
    from .data import Clausable, CourseInstance, AreaPointer  # noqa: F401

logger = logging.getLogger(__name__)
CACHE_SIZE = 2048


class ClauseMode(enum.Enum):
    Course = enum.auto()
    Area = enum.auto()
    Other = enum.auto()


@attr.s(auto_attribs=True, slots=True)
class BaseClause(abc.ABC):
    @lru_cache(CACHE_SIZE)
    def compare_and_resolve_with(self, value: Tuple['Clausable', ...]) -> 'Clause':
        raise NotImplementedError(f'must define a compare_and_resolve_with(value) method')

    @lru_cache(CACHE_SIZE)
    def apply(self, to: 'Clausable') -> bool:
        raise NotImplementedError(f'must define an apply(to=) method')


@attr.s(auto_attribs=True, slots=True)
class ClauseWithResult:
    mode: ClauseMode
    result: ResultStatus = ResultStatus.NotStarted

    def to_dict(self) -> Dict[str, Any]:
        return {
            "result": self.result.value,
            "rank": str(self.rank()),
            "max_rank": str(self.max_rank()),
        }

    @lru_cache(CACHE_SIZE)
    def rank(self) -> Union[int, Decimal]:
        if self.ok():
            return 1

        return 0

    @lru_cache(CACHE_SIZE)
    def max_rank(self) -> Union[int, Decimal]:
        if self.ok():
            return self.rank()

        return 1

    @lru_cache(CACHE_SIZE)
    @abc.abstractmethod
    def partially_complete(self) -> bool:
        raise NotImplementedError(f'must define a partially_complete() method')

    @lru_cache(CACHE_SIZE)
    @abc.abstractmethod
    def complete_after_current_term(self) -> bool:
        raise NotImplementedError(f'must define a complete_after_current_term() method')

    @lru_cache(CACHE_SIZE)
    @abc.abstractmethod
    def complete_after_registered(self) -> bool:
        raise NotImplementedError(f'must define a complete_after_registered() method')

    @lru_cache(CACHE_SIZE)
    @abc.abstractmethod
    def ok(self) -> bool:
        raise NotImplementedError(f'must define an ok() method')

    @lru_cache(CACHE_SIZE)
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


@attr.s(auto_attribs=True, slots=True)
class ResolvedClause(ClauseWithResult):
    resolved_with: Optional[Any] = None
    resolved_items: Tuple[Any, ...] = tuple()
    resolved_clbids: Tuple[str, ...] = tuple()
    in_progress_clbids: Tuple[str, ...] = tuple()
    future_clbids: Tuple[str, ...] = tuple()

    def to_dict(self) -> Dict[str, Any]:
        return {
            **super().to_dict(),
            "resolved_with": str(self.resolved_with) if self.resolved_with is not None else self.resolved_with,
            "resolved_items": [str(x) if isinstance(x, Decimal) else x for x in self.resolved_items],
            "resolved_clbids": [x for x in self.resolved_clbids],
            "in_progress_clbids": [x for x in self.in_progress_clbids],
            "future_clbids": [x for x in self.future_clbids],
        }


@attr.s(frozen=True, cache_hash=True, auto_attribs=True, slots=True)
class AndClause(BaseClause, ClauseWithResult):
    children: Tuple['Clause', ...] = tuple()

    def to_dict(self) -> Dict[str, Any]:
        return {
            **super().to_dict(),
            "type": "and-clause",
            "children": [c.to_dict() for c in self.children],
            "hash": str(hash(self.children)),
        }

    def validate(self, *, ctx: 'RequirementContext') -> None:
        for c in self.children:
            c.validate(ctx=ctx)

    @lru_cache(CACHE_SIZE)
    def apply(self, to: 'Clausable') -> bool:
        return all(subclause.apply(to) for subclause in self.children)

    @lru_cache(CACHE_SIZE)
    def compare_and_resolve_with(self, value: Tuple['Clausable', ...]) -> 'AndClause':  # type: ignore
        children = tuple(c.compare_and_resolve_with(value=value) for c in self.children)

        if all(c.complete_after_current_term() for c in children):
            result = ResultStatus.PendingCurrent
        elif all(c.complete_after_registered() for c in children):
            result = ResultStatus.PendingRegistered
        elif all(c.ok() for c in children):
            result = ResultStatus.Pass
        elif any(c.ok() for c in children):
            # if the number of done items is not fully complete
            result = ResultStatus.Partial
        else:
            result = ResultStatus.NotStarted

        return AndClause(children=children, result=result, mode=self.mode)

    @lru_cache(CACHE_SIZE)
    def ok(self) -> bool:
        return all(c.ok() for c in self.children)

    @lru_cache(CACHE_SIZE)
    def partially_complete(self) -> bool:
        return any(c.partially_complete() for c in self.children)

    @lru_cache(CACHE_SIZE)
    def complete_after_current_term(self) -> bool:
        return all(c.complete_after_current_term() for c in self.children)

    @lru_cache(CACHE_SIZE)
    def complete_after_registered(self) -> bool:
        return all(c.complete_after_registered() for c in self.children)

    @lru_cache(CACHE_SIZE)
    def rank(self) -> Union[int, Decimal]:
        return sum(c.rank() for c in self.children)

    @lru_cache(CACHE_SIZE)
    def max_rank(self) -> Union[int, Decimal]:
        if self.ok():
            return self.rank()

        return sum(c.max_rank() for c in self.children)


@attr.s(frozen=True, cache_hash=True, auto_attribs=True, slots=True)
class OrClause(BaseClause, ClauseWithResult):
    children: Tuple['Clause', ...] = tuple()

    def to_dict(self) -> Dict[str, Any]:
        return {
            **super().to_dict(),
            "type": "or-clause",
            "children": [c.to_dict() for c in self.children],
            "hash": str(hash(self.children)),
        }

    def validate(self, *, ctx: 'RequirementContext') -> None:
        for c in self.children:
            c.validate(ctx=ctx)

    @lru_cache(CACHE_SIZE)
    def apply(self, to: 'Clausable') -> bool:
        return any(subclause.apply(to) for subclause in self.children)

    @lru_cache(CACHE_SIZE)
    def compare_and_resolve_with(self, value: Tuple['Clausable', ...]) -> 'OrClause':  # type: ignore
        children = tuple(c.compare_and_resolve_with(value=value) for c in self.children)

        if any(c.complete_after_current_term() for c in children):
            result = ResultStatus.PendingCurrent
        elif any(c.complete_after_registered() for c in children):
            result = ResultStatus.PendingRegistered
        elif any(c.partially_complete() for c in children):
            result = ResultStatus.Partial
        elif any(c.ok() for c in children):
            result = ResultStatus.Pass
        else:
            # otherwise
            result = ResultStatus.NotStarted

        return OrClause(children=children, result=result, mode=self.mode)

    @lru_cache(CACHE_SIZE)
    def ok(self) -> bool:
        return any(c.ok() for c in self.children)

    @lru_cache(CACHE_SIZE)
    def partially_complete(self) -> bool:
        return any(c.partially_complete() for c in self.children)

    @lru_cache(CACHE_SIZE)
    def complete_after_current_term(self) -> bool:
        return any(c.complete_after_current_term() for c in self.children)

    @lru_cache(CACHE_SIZE)
    def complete_after_registered(self) -> bool:
        return any(c.complete_after_registered() for c in self.children)

    @lru_cache(CACHE_SIZE)
    def rank(self) -> Union[int, Decimal]:
        return sum(c.rank() for c in self.children)

    @lru_cache(CACHE_SIZE)
    def max_rank(self) -> Union[int, Decimal]:
        if self.ok():
            return self.rank()

        return sum(c.rank() if c.ok() else c.max_rank() for c in self.children)


def stringify_expected(expected: Any) -> Any:
    if isinstance(expected, tuple):
        return tuple(stringify_expected(e) for e in expected)

    if isinstance(expected, (GradeOption, GradeCode)):
        return expected.value

    elif isinstance(expected, Decimal):
        return str(expected)

    return expected


@attr.s(frozen=True, cache_hash=True, auto_attribs=True, slots=True)
class SingleClause(BaseClause, ResolvedClause):
    key: str = "???"
    expected: Any = None
    expected_verbatim: Any = None
    operator: Operator = Operator.EqualTo
    label: Optional[str] = None
    at_most: bool = False
    treat_in_progress_as_pass: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            **super().to_dict(),
            "type": "single-clause",
            "key": self.key,
            "expected": stringify_expected(self.expected),
            "expected_verbatim": stringify_expected(self.expected_verbatim),
            "operator": self.operator.name,
            "label": self.label,
            "ip_as_passing": self.treat_in_progress_as_pass,
            "hash": str(hash((self.key, self.expected, self.operator))),
        }

    @staticmethod
    def load(key: str, value: Any, *, c: Constants, mode: ClauseMode, forbid: Sequence[Operator] = tuple()) -> 'SingleClause':
        assert isinstance(value, Dict), Exception(f'expected {value} to be a dictionary')

        operators = [k for k in value.keys() if k.startswith('$')]
        assert len(operators) == 1, f"{value}"
        op = operators[0]
        operator = Operator(op)
        assert operator not in forbid, ValueError(f'operator {operator} is forbidden here - {forbid}')

        expected_value = value[op]
        if isinstance(expected_value, list):
            expected_value = tuple(expected_value)
        elif isinstance(expected_value, float):
            expected_value = Decimal(expected_value)

        expected_verbatim = expected_value

        key_lookup = {
            "subjects": "subject",
            "attribute": "attributes",
            "gereq": "gereqs",
        }
        key = key_lookup.get(key, key)

        allowed_types = (bool, str, tuple, int, Decimal)
        assert type(expected_value) in allowed_types, f"expected_value should be {allowed_types}, not {type(expected_value)}"

        if type(expected_value) == str:
            expected_value = c.get_by_name(expected_value)
        elif isinstance(expected_value, Iterable):
            expected_value = tuple(c.get_by_name(v) for v in expected_value)

        expected_value = process_clause_value(expected_value, key=key)

        if operator in (Operator.In, Operator.NotIn):
            assert all(v is not None for v in expected_value)
        else:
            assert expected_value is not None

        at_most = value.get('at_most', False)
        assert type(at_most) is bool

        return SingleClause(
            key=key,
            expected=expected_value,
            operator=operator,
            expected_verbatim=expected_verbatim,
            at_most=at_most,
            mode=mode,
            label=value.get('label', None),
            treat_in_progress_as_pass=value.get('treat_in_progress_as_pass', False),
        )

    def override_expected(self, value: Decimal) -> 'SingleClause':
        return attr.evolve(self, expected=value, expected_verbatim=str(value))

    @lru_cache(CACHE_SIZE)
    def ok(self) -> bool:
        return self.result is ResultStatus.Pass

    @lru_cache(CACHE_SIZE)
    def complete_after_current_term(self) -> bool:
        return self.result in (ResultStatus.Pass, ResultStatus.PendingCurrent)

    @lru_cache(CACHE_SIZE)
    def complete_after_registered(self) -> bool:
        return self.result in (ResultStatus.Pass, ResultStatus.PendingCurrent, ResultStatus.PendingRegistered)

    @lru_cache(CACHE_SIZE)
    def partially_complete(self) -> bool:
        return self.result in (ResultStatus.Pass, ResultStatus.PendingCurrent, ResultStatus.PendingRegistered, ResultStatus.Partial)

    @lru_cache(CACHE_SIZE)
    def rank(self) -> Union[int, Decimal]:
        if self.result is ResultStatus.Pass:
            return 1

        if self.operator not in (Operator.LessThan, Operator.LessThanOrEqualTo):
            if self.resolved_with is not None and type(self.resolved_with) in (int, Decimal):
                if type(self.expected) in (int, Decimal):
                    if self.expected != 0:
                        resolved = Decimal(self.resolved_with) / Decimal(self.expected)
                        return min(Decimal(1), resolved)

        return 0

    @lru_cache(CACHE_SIZE)
    def max_rank(self) -> Union[int, Decimal]:
        if self.ok():
            return self.rank()

        return 1

    def __repr__(self) -> str:
        return f"Clause({str_clause(self)})"

    def validate(self, *, ctx: 'RequirementContext') -> None:
        pass

    @lru_cache(CACHE_SIZE)
    def apply(self, to: 'Clausable') -> bool:
        return to.apply_single_clause(self)

    @lru_cache(CACHE_SIZE)
    def compare(self, to_value: Any) -> bool:
        return apply_operator(lhs=to_value, op=self.operator, rhs=self.expected)

    @lru_cache(CACHE_SIZE)
    def compare_and_resolve_with(self, value: Tuple['Clausable', ...]) -> 'SingleClause':  # type: ignore
        op = self.operator
        rhs = self.expected

        courses_only_completed = False
        courses_completed_ip = False
        courses_completed_ip_reg = False

        if self.mode is ClauseMode.Course:
            all_input_courses = cast(Sequence['CourseInstance'], value)
            input_courses = all_input_courses

            # try once with only completed clbids
            input_courses = [c for c in all_input_courses if c.is_completed]
            calculated_result = apply_clause_to_assertion_with_courses(self, input_courses)
            applied_result = apply_operator(lhs=calculated_result.value, op=op, rhs=rhs)

            if applied_result:
                courses_only_completed = True

            # try once with completed and IP clbids
            if not applied_result:
                input_courses = [c for c in all_input_courses if c.is_completed or c.is_current]
                calculated_result = apply_clause_to_assertion_with_courses(self, input_courses)
                applied_result = apply_operator(lhs=calculated_result.value, op=op, rhs=rhs)

                if applied_result:
                    courses_completed_ip = True

                # try once with all clbids
                if not applied_result:
                    courses_completed_ip_reg = True
                    input_courses = all_input_courses
                    calculated_result = apply_clause_to_assertion_with_courses(self, input_courses)
                    applied_result = apply_operator(lhs=calculated_result.value, op=op, rhs=rhs)

        elif self.mode is ClauseMode.Area:
            input_areas = cast(Sequence['AreaPointer'], value)
            calculated_result = apply_clause_to_assertion_with_areas(self, input_areas)
            applied_result = apply_operator(lhs=calculated_result.value, op=op, rhs=rhs)

        elif self.mode is ClauseMode.Other:
            calculated_result = apply_clause_to_assertion_with_data(self, value)
            applied_result = apply_operator(lhs=calculated_result.value, op=op, rhs=rhs)

        # # if we have `treat_in_progress_as_pass` set, we skip the ip_clbids check entirely
        # if ip_clbids and self.treat_in_progress_as_pass is False:
        #     result = ResultStatus.InProgress
        # elif apply_operator(lhs=reduced_value, op=self.operator, rhs=self.expected) is True:
        #     result = ResultStatus.Pass
        # elif clbids:
        #     # we aren't "passing", but we've also got at least something
        #     # counting towards this clause, so we'll mark it as in-progress.
        #     result = ResultStatus.InProgress
        # else:
        #     result = ResultStatus.NotStarted

        value_items = calculated_result.data
        clbids = calculated_result.clbids()
        ip_clbids = calculated_result.ip_clbids()
        future_clbids = calculated_result.future_clbids()

        if courses_only_completed and applied_result:
            result = ResultStatus.Pass
        elif courses_completed_ip and ip_clbids:
            result = ResultStatus.PendingCurrent
        elif courses_completed_ip_reg and future_clbids:
            result = ResultStatus.PendingRegistered
        elif clbids:
            # we aren't "passing", but we've also got at least something
            # counting towards this clause, so we'll mark it as in-progress.
            result = ResultStatus.Partial
        elif self.mode is not ClauseMode.Course and applied_result:
            # handle non-course data
            result = ResultStatus.Pass
        else:
            result = ResultStatus.NotStarted

        if self.operator in (Operator.LessThan, Operator.LessThanOrEqualTo)\
                and result in (ResultStatus.PendingCurrent, ResultStatus.Partial)\
                and apply_operator(lhs=reduced_value, op=self.operator, rhs=self.expected) is True:
            result = ResultStatus.Pass

        return SingleClause(
            mode=self.mode,
            key=self.key,
            expected=self.expected,
            expected_verbatim=self.expected_verbatim,
            operator=self.operator,
            at_most=self.at_most,
            label=self.label,
            resolved_with=calculated_result.value,
            resolved_items=tuple(value_items),
            resolved_clbids=clbids,
            in_progress_clbids=ip_clbids,
            future_clbids=future_clbids,
            result=result,
            treat_in_progress_as_pass=self.treat_in_progress_as_pass,
        )

    def input_size_range(self, *, maximum: int) -> Iterator[int]:
        if type(self.expected) is not int:
            raise TypeError('cannot find a range of values for a non-integer clause: %s', type(self.expected))

        if self.operator == Operator.EqualTo or (self.operator == Operator.GreaterThanOrEqualTo and self.at_most is True):
            if maximum < self.expected:
                yield maximum
                return
            yield from range(self.expected, self.expected + 1)

        elif self.operator == Operator.NotEqualTo:
            # from 0-maximum, skipping "expected"
            yield from range(0, self.expected)
            yield from range(self.expected + 1, max(self.expected + 1, maximum + 1))

        elif self.operator == Operator.GreaterThanOrEqualTo:
            if maximum < self.expected:
                yield maximum
                return
            yield from range(self.expected, max(self.expected + 1, maximum + 1))

        elif self.operator == Operator.GreaterThan:
            if maximum < self.expected:
                yield maximum
                return
            yield from range(self.expected + 1, max(self.expected + 2, maximum + 1))

        elif self.operator == Operator.LessThan:
            yield from range(0, self.expected)

        elif self.operator == Operator.LessThanOrEqualTo:
            yield from range(0, self.expected + 1)

        else:
            raise TypeError('unsupported operator for ranges %s', self.operator)


def process_clause__grade(expected_value: Any) -> Union[Decimal, Tuple[Decimal, ...]]:
    if type(expected_value) is str:
        try:
            return Decimal(expected_value)
        except InvalidOperation:
            return str_to_grade_points(expected_value)
    elif isinstance(expected_value, Iterable):
        return tuple(
            str_to_grade_points(v) if type(v) is str else Decimal(v)
            for v in expected_value
        )
    else:
        return Decimal(expected_value)


def process_clause__grade_option(expected_value: Any) -> GradeOption:
    return GradeOption(expected_value)


def process_clause__credits(expected_value: Any) -> Decimal:
    return Decimal(expected_value)


def process_clause__gpa(expected_value: Any) -> Decimal:
    return Decimal(expected_value)


clause_value_process: Mapping[str, Callable[[Sequence[Any]], Union[GradeOption, Decimal, Tuple[Decimal, ...]]]] = {
    'grade': process_clause__grade,
    'grade_option': process_clause__grade_option,
    'credits': process_clause__credits,
    'gpa': process_clause__gpa,
}


def process_clause_value(expected_value: Any, *, key: str) -> Union[Any, GradeOption, Decimal, Tuple[Decimal, ...]]:
    if key in clause_value_process:
        return clause_value_process[key](expected_value)

    return expected_value


def str_clause(clause: Union[Dict[str, Any], 'Clause']) -> str:
    if not isinstance(clause, dict):
        return str_clause(clause.to_dict())

    if clause["type"] == "single-clause":
        resolved_with = clause.get('resolved_with', None)
        if resolved_with is not None:
            resolved = f" ({repr(resolved_with)})"
        else:
            resolved = ""

        if clause['expected'] != clause['expected_verbatim']:
            postscript = f" (via {repr(clause['expected_verbatim'])})"
        else:
            postscript = ""

        label = clause['label']
        if label:
            postscript += f' [label: "{label}"]'

        op = str_operator(clause['operator'])

        return f'"{clause["key"]}"{resolved} {op} "{clause["expected"]}"{postscript}'
    elif clause["type"] == "or-clause":
        return f'({" or ".join(str_clause(c) for c in clause["children"])})'
    elif clause["type"] == "and-clause":
        return f'({" and ".join(str_clause(c) for c in clause["children"])})'

    raise Exception('not a clause')


def get_resolved_items(clause: Union[Dict[str, Any], 'Clause']) -> str:
    if not isinstance(clause, dict):
        return get_resolved_items(clause.to_dict())

    if clause["type"] == "single-clause":
        resolved_with = clause.get('resolved_with', None)
        if resolved_with is not None:
            return str(sorted(clause.get('resolved_items', [])))
        else:
            return ""
    elif clause["type"] == "or-clause":
        return f'({" or ".join(get_resolved_items(c) for c in clause["children"])})'
    elif clause["type"] == "and-clause":
        return f'({" and ".join(get_resolved_items(c) for c in clause["children"])})'

    raise Exception('not a clause')


def get_resolved_clbids(clause: Union[Dict[str, Any], 'Clause']) -> List[str]:
    if not isinstance(clause, dict):
        return get_resolved_clbids(clause.to_dict())

    if clause["type"] == "single-clause":
        return list(clause['resolved_clbids'])
    elif clause["type"] == "or-clause":
        return [clbid for c in clause["children"] for clbid in get_resolved_clbids(c)]
    elif clause["type"] == "and-clause":
        return [clbid for c in clause["children"] for clbid in get_resolved_clbids(c)]

    raise Exception('not a clause')


def get_in_progress_clbids(clause: Union[Dict[str, Any], 'Clause']) -> Set[str]:
    if not isinstance(clause, dict):
        return get_in_progress_clbids(clause.to_dict())

    if clause["type"] == "single-clause":
        return set(clause['in_progress_clbids'])
    elif clause["type"] == "or-clause":
        return set(clbid for c in clause["children"] for clbid in get_in_progress_clbids(c))
    elif clause["type"] == "and-clause":
        return set(clbid for c in clause["children"] for clbid in get_in_progress_clbids(c))

    raise Exception('not a clause')


def get_future_clbids(clause: Union[Dict[str, Any], 'Clause']) -> Set[str]:
    if not isinstance(clause, dict):
        return get_future_clbids(clause.to_dict())

    if clause["type"] == "single-clause":
        return set(clause['future_clbids'])
    elif clause["type"] == "or-clause":
        return set(clbid for c in clause["children"] for clbid in get_future_clbids(c))
    elif clause["type"] == "and-clause":
        return set(clbid for c in clause["children"] for clbid in get_future_clbids(c))

    raise Exception('not a clause')


Clause = Union[AndClause, OrClause, SingleClause]
