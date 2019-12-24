import attr
from typing import Dict, Mapping, List, Set, FrozenSet, Tuple, Optional, Iterator, Iterable, Any, TYPE_CHECKING
import logging
import decimal

from .base import Solution, Result, Rule, Base, Summable
from .constants import Constants
from .context import RequirementContext
from .data import CourseInstance, AreaPointer, AreaType, Student
from .limit import LimitSet
from .load_rule import load_rule
from .result.count import CountResult
from .result.requirement import RequirementResult
from .lib import grade_point_average
from .solve import find_best_solution
from .group_by import group_by

if TYPE_CHECKING:  # pragma: no cover
    from .claim import ClaimAttempt  # noqa: F401

logger = logging.getLogger(__name__)


@attr.s(cache_hash=True, slots=True, kw_only=True, frozen=True, auto_attribs=True)
class AreaOfStudy(Base):
    """The overall class for working with an area"""
    name: str
    kind: str
    degree: Optional[str]
    dept: Optional[str]
    code: str

    limit: LimitSet
    result: Any  # Rule
    multicountable: Dict[str, List[Tuple[str, ...]]]
    path: Tuple[str, ...]

    common_rules: Tuple[Rule, ...]
    excluded_clbids: FrozenSet[str] = frozenset()

    def to_dict(self) -> Dict[str, Any]:
        return {
            **super().to_dict(),
            "name": self.name,
            "kind": self.kind,
            "code": self.code,
            "degree": self.degree,
            "result": self.result.to_dict(),
            "gpa": str(self.gpa()),
            "limit": self.limit.to_dict(),
            "excluded": sorted(clbid for clbid in self.excluded_clbids),
        }

    def type(self) -> str:
        return "area"

    def gpa(self) -> decimal.Decimal:
        return decimal.Decimal('0.00')

    @staticmethod
    def load(
        *,
        specification: Mapping[str, Any],
        student: Student,
        all_emphases: bool = False,
        emphasis_validity_check: bool = False,
    ) -> 'AreaOfStudy':
        this_code = specification.get('code', '<null>')
        pointers = {p.code: p for p in student.areas}
        this_pointer = pointers.get(this_code, None)

        emphases = specification.get('emphases', {})

        # this block just does validity checking on the emphases; we don't
        # actually use the result of loading these here.
        for e in emphases.values():
            r = AreaOfStudy.load(specification=e, student=student, emphasis_validity_check=True)
            r.validate()

        declared_emphasis_codes = set(str(a.code) for a in student.areas if a.kind is AreaType.Emphasis)

        ctx = RequirementContext(student=student)

        result = load_rule(
            data=specification["result"],
            c=student.constants,
            children=specification.get("requirements", {}),
            emphases=[
                v for k, v in emphases.items()
                if str(k) in declared_emphasis_codes or all_emphases
            ],
            path=["$"],
            ctx=ctx,
        )
        assert result, TypeError(f'expected load_rule to process {specification["result"]}')

        # Automatically exclude any "required" courses
        excluded_clbids: FrozenSet[str] = frozenset()
        if not emphasis_validity_check:
            required_courses = result.get_required_courses(ctx=ctx)
            excluded_clbids = frozenset(c.clbid for c in required_courses)
            result = result.exclude_required_courses(required_courses)

            for crs in required_courses:
                logger.debug(f'excluding {crs.clbid} {crs.identity_}')

        limit = LimitSet.load(data=specification.get("limit", None), c=student.constants)

        multicountable_rules: Dict[str, List[Tuple[str, ...]]] = {
            course: [
                tuple(f"%{segment}" for segment in path)
                for path in paths
            ]
            for course, paths in specification.get("multicountable", {}).items()
        }

        allowed_keys = {'name', 'type', 'major', 'degree', 'code', 'emphases', 'result', 'requirements', 'limit', 'multicountable'}
        given_keys = set(specification.keys())
        assert given_keys.difference(allowed_keys) == set(), f"expected set {given_keys.difference(allowed_keys)} to be empty (at ['$'])"

        dept = this_pointer.dept if this_pointer else None
        degree = specification.get('degree', None)

        return AreaOfStudy(
            name=specification.get('name', 'Test'),
            kind=specification.get('type', 'test'),
            degree=degree,
            dept=dept,
            result=result,
            multicountable=multicountable_rules,
            limit=limit,
            path=('$',),
            code=this_code,
            excluded_clbids=excluded_clbids,
            common_rules=tuple(prepare_common_rules(
                other_areas=student.areas,
                dept_code=dept,
                degree=degree,
                area_code=this_code,
            ))
        )

    def validate(self) -> None:
        ctx = RequirementContext()

        self.result.validate(ctx=ctx)

    def solutions(self, *, student: Student) -> Iterable['AreaSolution']:
        logger.debug("evaluating area.result")

        ctx = RequirementContext(student=student)
        ctx.claims.multicountable = self.multicountable

        for limited_transcript in self.limit.limited_transcripts(courses=student.transcript.courses):
            logger.debug("%s evaluating area.result with limited transcript", limited_transcript)

            ctx = ctx.with_limited_transcript(limited_transcript)

            for sol in self.result.solutions(ctx=ctx, depth=1):
                # be sure to start with an empty claims list - without
                # clearing it here, these calls only work if you process the
                # `.audit()` calls in sequence directly from the generator;
                # generating a full list of all solutions and then iterating
                # over that will accidentally share state.
                yield AreaSolution.from_area(solution=sol, area=self, ctx=ctx.with_empty_claims())

        logger.debug("all solutions generated")

    def estimate(self, *, student: Student) -> int:
        ctx = RequirementContext(student=student)
        ctx.claims.multicountable = self.multicountable

        acc = 0

        for limited_transcript in self.limit.limited_transcripts(courses=student.transcript.courses):
            ctx = ctx.with_limited_transcript(limited_transcript)
            acc += self.result.estimate(ctx=ctx.with_empty_claims(), depth=1)

        return acc


@attr.s(cache_hash=True, slots=True, kw_only=True, frozen=True, auto_attribs=True)
class AreaSolution(AreaOfStudy):
    solution: Solution
    context: RequirementContext

    @staticmethod
    def from_area(*, area: AreaOfStudy, solution: Solution, ctx: RequirementContext) -> 'AreaSolution':
        return AreaSolution(
            name=area.name,
            kind=area.kind,
            dept=area.dept,
            code=area.code,
            degree=area.degree,
            limit=area.limit,
            result=area.result,
            multicountable=area.multicountable,
            path=area.path,
            solution=solution,
            context=ctx,
            common_rules=area.common_rules,
            excluded_clbids=area.excluded_clbids,
        )

    def audit(self) -> 'AreaResult':
        result = self.solution.audit(ctx=self.context)

        # Append the "common" major requirements, if we've audited a major.
        if self.kind == 'major':
            common_req_results = self.audit_common_major_requirements(result=result)

            assert isinstance(result, CountResult), TypeError('expected a Count result from common major requirements')

            result = attr.evolve(result, items=tuple([*result.items, common_req_results]), count=result.count + 1)

        return AreaResult.from_solution(area=self, result=result, ctx=self.context)

    def audit_common_major_requirements(self, result: Result) -> RequirementResult:
        claimed: Set[CourseInstance] = result.matched()
        # unclaimed = list(set(self.context.transcript()) - claimed)
        # unclaimed_context = RequirementContext().with_transcript(unclaimed)
        fresh_context = attr.evolve(self.context)
        whole_context = fresh_context.with_limited_transcript(fresh_context.student.transcript.including_excluded())
        claimed_context = fresh_context.with_limited_transcript(claimed)

        c_or_better = self.common_rules[0]
        s_u_credits = self.common_rules[1]
        outside_the_major = self.common_rules[2] if len(self.common_rules) > 2 else None

        with claimed_context.fresh_claims():
            c_or_better__result = find_best_solution(rule=c_or_better, ctx=claimed_context)
            assert c_or_better__result is not None, TypeError('no solutions found for c_or_better rule')

        with claimed_context.fresh_claims():
            s_u_credits__result = find_best_solution(rule=s_u_credits, ctx=claimed_context)
            assert s_u_credits__result is not None, TypeError('no solutions found for s_u_credits__result rule')

        outside_the_major__result = None
        if outside_the_major:
            # with unclaimed_context.fresh_claims():
            outside_the_major__result = find_best_solution(rule=outside_the_major, ctx=whole_context)
            assert outside_the_major__result is not None, TypeError('no solutions found for outside_the_major__result rule')

        items = [c_or_better__result, s_u_credits__result]
        if outside_the_major__result is not None:
            items.append(outside_the_major__result)

        return RequirementResult(
            name=f"Common {self.degree} Major Requirements",
            message=None,
            path=('$', '%Common Requirements'),
            audited_by=None,
            in_gpa=False,
            is_contract=False,
            overridden=False,
            disjoint=None,
            result=CountResult(
                path=('$', '%Common Requirements', '.count'),
                count=len(items),
                at_most=False,
                audit_clauses=tuple(),
                audit_results=tuple(),
                overridden=False,
                items=tuple(items),
            ),
        )


@attr.s(cache_hash=True, slots=True, kw_only=True, frozen=True, auto_attribs=True)
class AreaResult(AreaOfStudy, Result):
    result: Result
    context: RequirementContext

    @staticmethod
    def from_solution(*, area: AreaOfStudy, result: Result, ctx: RequirementContext) -> 'AreaResult':
        return AreaResult(
            name=area.name,
            kind=area.kind,
            dept=area.dept,
            code=area.code,
            degree=area.degree,
            limit=area.limit,
            multicountable=area.multicountable,
            path=area.path,
            context=ctx,
            result=result,
            common_rules=area.common_rules,
            excluded_clbids=area.excluded_clbids,
        )

    def gpa(self) -> decimal.Decimal:
        if not self.result:
            return decimal.Decimal('0.00')

        if self.kind == 'degree':
            courses = list(self.context.student.transcript.gpa_items())
        else:
            courses = list(self.matched_for_gpa())

        return grade_point_average(courses)

    def ok(self) -> bool:
        if self.was_overridden():
            return True

        return self.result.ok()

    def rank(self) -> Summable:
        return self.result.rank()

    def max_rank(self) -> Summable:
        return self.result.max_rank()

    def claims(self) -> List['ClaimAttempt']:
        return self.result.claims()

    def keyed_claims(self) -> Dict[str, List[List[str]]]:
        def sort_claims_by_time(cl: 'ClaimAttempt') -> Tuple:
            c = cl.claim.course
            return (c.subject, c.number, c.section or '', c.sub_type.value, c.year, c.term)

        claims = sorted((c for c in self.claims() if not c.failed), key=sort_claims_by_time)
        by_clbid = group_by(claims, key=lambda c: c.claim.course.clbid)

        return {
            clbid: [list(attempt.claim.claimant_path) for attempt in claim_attempts]
            for clbid, claim_attempts in by_clbid.items()
        }

    def claims_for_gpa(self) -> List['ClaimAttempt']:
        return self.result.claims_for_gpa()

    def was_overridden(self) -> bool:
        return self.result.was_overridden()


def prepare_common_rules(
    *,
    degree: Optional[str],
    dept_code: Optional[str],
    other_areas: Tuple[AreaPointer, ...] = tuple(),
    area_code: str,
) -> Iterator[Rule]:
    c = Constants(matriculation_year=0)

    other_area_codes = set(p.code for p in other_areas if p.code != area_code)

    studio_art_code = '140'
    art_history_code = '135'
    is_history_and_studio = \
        (area_code == studio_art_code and art_history_code in other_area_codes)\
        or (area_code == art_history_code and studio_art_code in other_area_codes)

    if is_history_and_studio:
        credits_message = " Students who double-major in studio art and art history are required to complete at least 18 full-course credits outside the SIS 'ART' subject code."
        credits_outside_major = 18
    else:
        credits_message = ""
        credits_outside_major = 21

    if degree == 'B.M.':
        is_bm_major = True
    else:
        is_bm_major = False

    c_or_better = load_rule(
        data={"requirement": "Credits at a C or higher"},
        children={
            "Credits at a C or higher": {
                "message": "Of the credits counting toward the minimum requirements for a major, a total of six (6.00) must be completed with a grade of C or higher.",
                "result": {
                    "from": "courses",
                    "allow_claimed": True,
                    "claim": False,
                    "where": {
                        "$and": [
                            {
                                "$or": [
                                    {"grade": {"$gte": "C"}},
                                    {"is_in_progress": {"$eq": True}},
                                ]
                            },
                            {"credits": {"$gt": 0}},
                        ],
                    },
                    "assert": {"sum(credits)": {"$gte": 6}},
                },
            },
        },
        path=['$', '%Common Requirements', '.count', '[0]'],
        c=c,
        ctx=RequirementContext(),
    )

    assert c_or_better is not None, TypeError('expected c_or_better to not be None')

    yield c_or_better

    if is_bm_major:
        s_u_detail = {
            "message": "No courses in a B.M Music major may be taken S/U.",
            "result": {
                "from": "courses",
                "allow_claimed": True,
                "claim": False,
                "where": {"s/u": {"$eq": True}},
                "assert": {"count(courses)": {"$eq": 0}},
            },
        }
    else:
        s_u_detail = {
            "message": "Only one full-course equivalent (1.00-credit course) taken S/U may count toward the minimum requirements for a major.",
            "result": {
                "from": "courses",
                "allow_claimed": True,
                "claim": False,
                "where": {
                    "$and": [
                        {"s/u": {"$eq": True}},
                        {"credits": {"$eq": 1}},
                    ],
                },
                "assert": {"count(courses)": {"$lte": 1}},
            },
        }

    s_u_credits = load_rule(
        data={"requirement": "Credits taken S/U"},
        children={"Credits taken S/U": s_u_detail},
        path=['$', '%Common Requirements', '.count', '[1]'],
        c=c,
        ctx=RequirementContext(),
    )

    assert s_u_credits is not None, TypeError('expected s_u_credits to not be None')

    yield s_u_credits

    if is_bm_major is False:
        if dept_code is None:
            outside_rule = {
                "message": f"21 total credits must be completed outside of the SIS 'subject' code of the major ({dept_code}).{credits_message}",
                "registrar_audited": True,
            }
        else:
            outside_rule = {
                "message": f"21 total credits must be completed outside of the SIS 'subject' code of the major ({dept_code}).{credits_message}",
                "result": {
                    "from": "courses",
                    "where": {
                        "$and": [
                            {"subject": {"$neq": dept_code}},
                            {"subject": {"$neq": "REG"}},
                        ],
                    },
                    "allow_claimed": True,
                    "claim": False,
                    "assert": {"sum(credits)": {"$gte": credits_outside_major}},
                },
            }

        outside_the_major = load_rule(
            data={"requirement": "Credits outside the major"},
            children={"Credits outside the major": outside_rule},
            path=['$', '%Common Requirements', '.count', '[2]'],
            c=c,
            ctx=RequirementContext(),
        )
        assert outside_the_major is not None, TypeError('expected outside_the_major to not be None')

        yield outside_the_major
