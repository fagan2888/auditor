import attr
from typing import Iterable, Optional, Tuple, Dict, Sequence, Iterator, FrozenSet, Mapping, Any
import logging
from decimal import Decimal

from ..base.course import BaseCourseRule
from ..exception import RuleException, OverrideException, InsertionException, ValueException, load_exception
from ..constants import Constants
from .area_pointer import AreaPointer
from .course import CourseInstance, load_course
from .course_enums import CourseType, GradeOption, TranscriptCode, GradeCode
from ..lib import grade_point_average_items, grade_point_average
from .music import MusicPerformance, MusicAttendance, MusicProficiencies

logger = logging.getLogger(__name__)


@attr.s(slots=True, kw_only=True, frozen=True, auto_attribs=True)
class StudentExceptions:
    exceptions: Tuple[RuleException, ...] = tuple()
    exception_paths: FrozenSet[Tuple[str, ...]] = frozenset()

    def __attrs_post_init__(self) -> None:
        exception_paths = frozenset(e.path for e in self.exceptions)
        object.__setattr__(self, "exception_paths", exception_paths)

    @staticmethod
    def load(data: Sequence[Mapping[str, Any]], *, code: str) -> 'StudentExceptions':
        exceptions = tuple(
            load_exception(e)
            for e in data
            if e['area_code'] == code
        )

        return StudentExceptions(exceptions=exceptions)

    def has_exception(self, path: Tuple[str, ...]) -> bool:
        return any(e.path[:len(path)] == path for e in self.exceptions)

    def get_forced_clbids(self) -> Iterator[str]:
        for exception in self.exceptions:
            if isinstance(exception, InsertionException) and exception.forced:
                yield exception.clbid

    def get_insert_exceptions(self, path: Tuple[str, ...]) -> Iterator[InsertionException]:
        if path not in self.exception_paths:
            return

        did_yield = False
        for exception in self.exceptions:
            if isinstance(exception, InsertionException) and exception.path == path:
                logger.debug("exception found for %s: %s", path, exception)
                did_yield = True
                yield exception

        if not did_yield:
            logger.debug("no exception for %s", path)

    def get_waive_exception(self, path: Tuple[str, ...]) -> Optional[OverrideException]:
        if path not in self.exception_paths:
            return None

        for e in self.exceptions:
            if isinstance(e, OverrideException) and e.path == path:
                logger.debug("exception found for %s: %s", path, e)
                return e

        logger.debug("no exception for %s", path)
        return None

    def get_value_exception(self, path: Tuple[str, ...]) -> Optional[ValueException]:
        if path not in self.exception_paths:
            return None

        for e in self.exceptions:
            if isinstance(e, ValueException) and e.path == path:
                logger.debug("exception found for %s: %s", path, e)
                return e

        logger.debug("no exception for %s", path)
        return None


@attr.s(slots=True, kw_only=True, frozen=False, auto_attribs=True)
class Transcript:
    courses: Tuple[CourseInstance, ...] = ()
    course_set: FrozenSet[str] = frozenset()
    by_clbid: Dict[str, CourseInstance] = attr.ib(factory=dict)

    excluded: Tuple[CourseInstance, ...] = ()
    failed: Tuple[CourseInstance, ...] = ()
    forced: Tuple[CourseInstance, ...] = ()

    @staticmethod
    def blank() -> 'Transcript':
        return Transcript()

    def __attrs_post_init__(self) -> None:
        course_set = frozenset(c.course() for c in self.courses)
        by_clbid = {c.clbid: c for c in self.courses}

        object.__setattr__(self, "course_set", course_set)
        object.__setattr__(self, "by_clbid", by_clbid)

    @staticmethod
    def load(data: Sequence[Mapping[str, Any]], *, exceptions: StudentExceptions) -> 'Transcript':
        forced_by_exception = set(clbid for clbid in exceptions.get_forced_clbids())

        audited = []
        failed = []
        forced = []
        valid = []

        for row in data:
            c = load_course(row)

            if c.clbid in forced_by_exception:
                forced.append(c)

            # excluded Audited courses
            if (c.grade_option is GradeOption.Audit) or (c.grade_code is GradeCode._AU):
                audited.append(c)
                continue

            # excluded repeated courses
            if c.transcript_code in (TranscriptCode.RepeatedLater, TranscriptCode.RepeatInProgress):
                continue

            # exclude [N]o-Pass, [U]nsuccessful, [AU]dit, [UA]nsuccessfulAudit, [WF]ithdrawnFail, [WP]ithdrawnPass, and [Withdrawn]
            if c.grade_code in (GradeCode._N, GradeCode._U, GradeCode._AU, GradeCode._UA, GradeCode._WF, GradeCode._WP, GradeCode._W):
                continue

            # exclude courses at grade F
            if c.grade_code is GradeCode.F:
                failed.append(c)
                continue

            valid.append(c)

        return Transcript(courses=Transcript.ordered_courses(valid))

    def with_limited_transcript(self, courses: Iterable[CourseInstance]) -> 'Transcript':
        return attr.evolve(self, courses=Transcript.ordered_courses(courses))

    @classmethod
    def ordered_courses(cls, courses: Iterable[CourseInstance]) -> Tuple[CourseInstance, ...]:
        return tuple(sorted(courses, key=lambda course: course.sort_order()))

    def gpa_items(self) -> Iterator[CourseInstance]:
        yield from grade_point_average_items(self.courses)
        yield from grade_point_average_items(self.failed)

    def gpa(self) -> Decimal:
        return grade_point_average(self.gpa_items())

    def including_excluded(self) -> Iterator[CourseInstance]:
        yield from self.courses
        yield from self.forced
        yield from self.excluded

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

        for c in self.courses:
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
        return self.by_clbid.get(clbid, None)

    def forced_course_by_clbid(self, clbid: str, path: Sequence[str]) -> CourseInstance:
        match = self.find_course_by_clbid(clbid)
        if not match:
            forced_clbid_lookup_map = {c.clbid: c for c in self.forced}
            match = forced_clbid_lookup_map.get(clbid, None)
        if not match:
            raise Exception(f'attempted to use CLBID={clbid} at {list(path)}, but it was not found in the transcript')
        return match

    def has_course(self, c: str) -> bool:
        return c in self.course_set


@attr.s(slots=True, kw_only=True, frozen=False, auto_attribs=True)
class Student:
    areas: Tuple[AreaPointer, ...] = tuple()
    constants: Constants = Constants(matriculation_year=0)
    exceptions: StudentExceptions = StudentExceptions()
    music_attendances: Tuple[MusicAttendance, ...] = tuple()
    music_performances: Tuple[MusicPerformance, ...] = tuple()
    music_proficiencies: MusicProficiencies = MusicProficiencies()
    transcript: Transcript = Transcript()

    @staticmethod
    def load(data: Mapping[str, Any], *, for_area_code: Optional[str] = None, ex: Iterable[RuleException] = tuple()) -> 'Student':
        areas = tuple(AreaPointer.from_dict(a) for a in data.get('areas', []))

        matriculation: int = 0 if data.get('matriculation', '') == '' else int(data['matriculation'])
        constants = Constants(matriculation_year=matriculation)

        if for_area_code:
            exceptions = StudentExceptions.load(data.get('exceptions', []), code=for_area_code)
        else:
            exceptions = StudentExceptions()

        if ex:
            exceptions = StudentExceptions(exceptions=tuple(ex))

        courses = Transcript.load(data.get('courses', []), exceptions=exceptions)

        _performances = (MusicPerformance.from_dict(d) for d in data.get('performances', []))
        _attendances = (MusicAttendance.from_dict(d) for d in data.get('performance_attendances', []))

        music_performances = tuple(sorted(_performances, key=lambda p: p.sort_order()))
        music_attendances = tuple(sorted(_attendances, key=lambda a: a.sort_order()))
        music_proficiencies = MusicProficiencies.from_dict(data.get('proficiencies', {}))

        return Student(
            areas=areas,
            constants=constants,
            exceptions=exceptions,
            music_performances=music_performances,
            music_attendances=music_attendances,
            music_proficiencies=music_proficiencies,
            transcript=courses,
        )

    def with_limited_transcript(self, courses: Iterable[CourseInstance]) -> 'Student':
        return attr.evolve(self, transcript=self.transcript.with_limited_transcript(courses))

    def has_area_code(self, code: str) -> bool:
        return any(code == c.code for c in self.areas)
