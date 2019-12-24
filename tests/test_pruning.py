from degreepath.data import course_from_str, Student
from degreepath.area import AreaOfStudy
from degreepath.constants import Constants
from degreepath.result.course import CourseResult
import logging

c = Constants(matriculation_year=2000)


def test_pruning_on_count_rule(caplog):
    caplog.set_level(logging.DEBUG)

    course_a = course_from_str("DEPT 123", clbid="0")
    course_b = course_from_str("DEPT 234", clbid="1")
    transcript = [course_a, course_b]

    s = Student.load({'courses': transcript})

    area = AreaOfStudy.load(specification={
        "result": {
            "any": [
                {"course": "DEPT 123"},
                {"course": "DEPT 234"},
                {"course": "DEPT 345"},
            ],
        },
    }, student=s)

    solutions = list(area.solutions(student=s))

    assert [
        [x.course for x in s.solution.items if isinstance(x, CourseResult)]
        for s in solutions
    ] == [['DEPT 123', 'DEPT 234']]
    assert len(solutions) == 1

    result = solutions[0].audit()

    assert result.result.count == 1
    assert result.ok() is True
    assert result.was_overridden() is False
    assert result.claims()[0].claim.course.clbid == course_a.clbid
