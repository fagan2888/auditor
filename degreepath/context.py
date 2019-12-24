import attr
from typing import List, Optional, Tuple, Sequence, Iterable, Iterator
from contextlib import contextmanager
import logging

from .base.course import BaseCourseRule
from .data import CourseInstance, Student
from .data.course_enums import CourseType
from .claim import ClaimAttempt
from .exception import OverrideException, InsertionException, ValueException

from .data.claims import CourseClaims

logger = logging.getLogger(__name__)
debug: Optional[bool] = None


@attr.s(slots=True, kw_only=True, frozen=False, auto_attribs=True)
class RequirementContext:
    student: Student = Student()
    claims: CourseClaims = CourseClaims()

    def with_limited_transcript(self, courses: Iterable[CourseInstance]) -> 'RequirementContext':
        return attr.evolve(self, student=self.student.with_limited_transcript(courses))

    def transcript(self) -> List[CourseInstance]:
        return list(self.student.transcript.courses)

    def all_claimed(self) -> List[CourseInstance]:
        return [self.student.transcript.by_clbid[clbid] for clbid in self.claims.claims.keys()]

    def find_courses(self, *, rule: BaseCourseRule, from_claimed: bool = False) -> Iterator[CourseInstance]:
        if rule.clbid:
            match_by_clbid = self.find_course_by_clbid(rule.clbid)
            if match_by_clbid:
                yield match_by_clbid
            return

        ap = rule.ap
        course = rule.course
        institution = rule.institution
        name = rule.name

        query = (course, name, ap, institution, CourseType.AP if ap else None)

        source = self.transcript() if not from_claimed else self.all_claimed()

        for c in source:
            if not c.is_stolaf and institution is None and ap is None:
                continue

            matcher = (
                c.identity_ if course else None,
                c.name if name else None,
                c.name if ap else None,
                c.institution if institution else None,
                c.course_type if ap else None,
            )

            if query == matcher:
                yield c

    def find_course_by_clbid(self, clbid: str) -> Optional[CourseInstance]:
        return self.student.transcript.by_clbid.get(clbid, None)

    def forced_course_by_clbid(self, clbid: str, path: Sequence[str]) -> CourseInstance:
        return self.student.transcript.forced_course_by_clbid(clbid, path)

    def has_area_code(self, code: str) -> bool:
        return self.student.has_area_code(code)

    def has_course(self, c: str) -> bool:
        return c in self.student.transcript.course_set

    def has_exception(self, path: Tuple[str, ...]) -> bool:
        return self.student.exceptions.has_exception(path)

    def get_insert_exceptions(self, path: Tuple[str, ...]) -> Iterator[InsertionException]:
        return self.student.exceptions.get_insert_exceptions(path)

    def get_waive_exception(self, path: Tuple[str, ...]) -> Optional[OverrideException]:
        return self.student.exceptions.get_waive_exception(path)

    def get_value_exception(self, path: Tuple[str, ...]) -> Optional[ValueException]:
        return self.student.exceptions.get_value_exception(path)

    @contextmanager
    def fresh_claims(self) -> Iterator[None]:
        claims = self.claims
        self.reset_claims()

        try:
            yield
        finally:
            self.set_claims(claims)

    def set_claims(self, claims: CourseClaims) -> None:
        self.claims = claims

    def reset_claims(self) -> None:
        self.claims = self.claims.with_empty_claims()

    def make_claim(self, *, course: CourseInstance, path: Tuple[str, ...], allow_claimed: bool = False) -> ClaimAttempt:
        return self.claims.make_claim(course=course, path=path, allow_claimed=allow_claimed)

    def with_empty_claims(self) -> 'RequirementContext':
        return attr.evolve(self, claims=self.claims.with_empty_claims())

    def merge_claims(self, *claims: CourseClaims) -> None:
        self.claims = self.claims.merge_claims(*claims)
