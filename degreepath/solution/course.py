from dataclasses import dataclass
import logging

from ..base import Solution, BaseCourseRule
from ..result.course import CourseResult

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CourseSolution(Solution, BaseCourseRule):
    overridden: bool = False

    @staticmethod
    def from_rule(*, rule: BaseCourseRule, overridden: bool = False):
        return CourseSolution(
            course=rule.course,
            hidden=rule.hidden,
            grade=rule.grade,
            allow_claimed=rule.allow_claimed,
            path=rule.path,
            overridden=overridden,
        )

    def __repr__(self):
        return self.course

    def audit(self, *, ctx):
        if self.overridden:
            return CourseResult.from_solution(solution=self, overridden=self.overridden)

        exception = ctx.get_exception(self.path)
        if exception and exception.is_insertion():
            matched_course = ctx.forced_course_by_clbid(exception.clbid)

        else:
            matched_course = ctx.find_course(self.course)

            if matched_course is None:
                logger.debug('%s course "%s" does not exist in the transcript', self.path, self.course)
                return CourseResult.from_solution(solution=self, claim_attempt=None)

            if self.grade is not None and matched_course.grade_points < self.grade:
                logger.debug('%s course "%s" exists, but the grade of %s is below the allowed minimum grade of %s', self.path, self.course, matched_course.grade_points, self.grade)
                return CourseResult.from_solution(solution=self, claim_attempt=None, min_grade_not_met=matched_course)

        claim = ctx.make_claim(course=matched_course, path=self.path, clause=self)

        if claim.failed():
            logger.debug('%s course "%s" exists, but has already been claimed by %s', self.path, self.course, claim.conflict_with)
            return CourseResult.from_solution(solution=self, claim_attempt=claim)

        logger.debug('%s course "%s" exists, and has not been claimed', self.path, self.course)

        return CourseResult.from_solution(solution=self, claim_attempt=claim)
