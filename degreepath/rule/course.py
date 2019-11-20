import attr
from typing import Dict, List, Iterator, Collection, Optional, TYPE_CHECKING
import re
import logging

from ..base import Rule, BaseCourseRule
from ..constants import Constants
from ..lib import str_to_grade_points
from ..solution.course import CourseSolution
from ..data.course_enums import GradeOption

if TYPE_CHECKING:  # pragma: no cover
    from ..context import RequirementContext
    from ..data import Clausable  # noqa: F401

logger = logging.getLogger(__name__)


@attr.s(cache_hash=True, slots=True, kw_only=True, frozen=True, auto_attribs=True)
class CourseRule(Rule, BaseCourseRule):
    @staticmethod
    def can_load(data: Dict) -> bool:
        if "course" in data:
            return True
        if "ap" in data:
            return True
        return False

    @staticmethod
    def load(data: Dict, *, c: Constants, path: List[str]) -> 'CourseRule':
        course = data.get('course', None)
        ap = data.get('ap', None)
        name = data.get('name', None)
        institution = data.get('institution', None)
        min_grade = data.get('grade', None)
        grade_option = data.get('grade_option', None)

        path_name = f"*{course or ap}"
        path_inst = f"(institution={institution})" if institution else ""
        path_grade = f"(grade >= {min_grade})" if min_grade else ""
        path = [*path, f"{path_name}{path_inst}{path_grade}"]

        allowed_keys = {'course', 'grade', 'allow_claimed', 'including claimed', 'hidden', 'ap', 'grade_option', 'institution', 'name'}
        given_keys = set(data.keys())
        assert given_keys.difference(allowed_keys) == set(), f"expected set {given_keys.difference(allowed_keys)} to be empty (at {path})"

        return CourseRule(
            course=course,
            hidden=data.get("hidden", False),
            grade=str_to_grade_points(min_grade) if min_grade is not None else None,
            grade_option=GradeOption(grade_option) if grade_option else None,
            allow_claimed=data.get("including claimed", data.get("allow_claimed", False)),
            path=tuple(path),
            institution=institution,
            name=name,
            ap=ap,
        )

    def validate(self, *, ctx: 'RequirementContext') -> None:
        if self.course:
            method_a = re.match(r"[A-Z]{3,5} [0-9]{3}", self.course)
            method_b = re.match(r"[A-Z]{2}/[A-Z]{2} [0-9]{3}", self.course)
            method_c = re.match(r"(IS|ID) [0-9]{3}", self.course)

            assert (method_a or method_b or method_c) is not None, f"{self.course}, {method_a}, {method_b}, {method_c}"

        assert self.course or self.ap or (self.institution and self.name)

    def get_requirement_names(self) -> List[str]:
        return []

    def solutions(self, *, ctx: 'RequirementContext', depth: Optional[int] = None) -> Iterator[CourseSolution]:
        if ctx.get_waive_exception(self.path):
            logger.debug("forced override on %s", self.path)
            yield CourseSolution.from_rule(rule=self, overridden=True)
            return

        logger.debug('%s reference to course "%s"', self.path, self.course)

        yield CourseSolution.from_rule(rule=self)

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

        try:
            next(ctx.find_courses(course=self.course, ap=self.ap, institution=self.institution))
            return True
        except StopIteration:
            return False

    def all_matches(self, *, ctx: 'RequirementContext') -> Collection['Clausable']:
        for insert in ctx.get_insert_exceptions(self.path):
            match = ctx.find_course_by_clbid(insert.clbid)
            return [match] if match else []

        return list(ctx.find_courses(course=self.course, ap=self.ap, institution=self.institution))
