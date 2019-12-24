from degreepath.area import AreaOfStudy
from degreepath.data import course_from_str, Student
from degreepath.constants import Constants
import pytest
import io
import yaml
import logging

c = Constants(matriculation_year=2000)


def test_from(caplog):
    caplog.set_level(logging.DEBUG)

    transcript = [
        course_from_str("CSCI 111", gereqs=['SPM'], term=20081),
        course_from_str("ASIAN 110"),
    ]
    student = Student.load({'courses': transcript})

    test_data = io.StringIO("""
        result:
            from: courses
            where: {gereqs: {$eq: SPM}}
            assert: {count(courses): {$gte: 1}}
    """)

    area = AreaOfStudy.load(specification=yaml.load(stream=test_data, Loader=yaml.SafeLoader), student=student)

    s = next(area.solutions(student=student))
    a = s.audit().result

    assert len(a.successful_claims) == 1

    assert a.successful_claims[0].claim.course.clbid == transcript[0].clbid


def __get_data(spec):
    transcript = [
        course_from_str("CSCI 113", gereqs=['SPM'], term=20071),
        course_from_str("CSCI 112", gereqs=['SPM'], term=20081),
        course_from_str("CSCI 111", gereqs=['SPM'], term=20091),
    ]

    s = Student.load({'courses': transcript})

    area = AreaOfStudy.load(specification=yaml.load(stream=io.StringIO(spec), Loader=yaml.SafeLoader), student=s)

    return (area, transcript, s)


def test_solution_count_exact(caplog):
    caplog.set_level(logging.DEBUG, logger='degreepath.rule.given.rule')

    area, transcript, student = __get_data("""
        result:
            from: courses
            where: {gereqs: {$eq: SPM}}
            assert: {count(courses): {$eq: 1}}
    """)

    solutions = area.solutions(student=student)

    sol = next(solutions)
    assert len(sol.solution.output) == 1

    sol = next(solutions)
    assert len(sol.solution.output) == 1

    sol = next(solutions)
    assert len(sol.solution.output) == 1

    with pytest.raises(StopIteration):
        next(solutions)


def test_solution_count_lessthan(caplog):
    caplog.set_level(logging.DEBUG, logger='degreepath.rule.given.rule')

    with pytest.raises(AssertionError):
        area, transcript = __get_data("""
            result:
                requirement: Test

            requirements:
                Test:
                    result:
                        from: courses
                        where: {gereqs: {$eq: SPM}}
                        assert: {count(courses): {$lt: 3}}
        """)


def test_solution_count_greaterthan_1(caplog):
    caplog.set_level(logging.DEBUG, logger='degreepath.rule.given.rule')
    area, transcript, student = __get_data("""
        result:
            from: courses
            where: {gereqs: {$eq: SPM}}
            assert: {count(courses): {$gt: 1}}
    """)

    solutions = area.solutions(student=student)

    sol = next(solutions)
    assert len(sol.solution.output) == 2

    sol = next(solutions)
    assert len(sol.solution.output) == 2

    sol = next(solutions)
    assert len(sol.solution.output) == 2

    sol = next(solutions)
    assert len(sol.solution.output) == 3

    with pytest.raises(StopIteration):
        next(solutions)


def test_solution_count_always_yield_something(caplog):
    caplog.set_level(logging.DEBUG, logger='degreepath.rule.given.rule')
    area, transcript, student = __get_data("""
        result:
            from: courses
            where: {gereqs: {$eq: FOOBAR}}
            assert: {count(courses): {$gt: 1}}
    """)

    solutions = area.solutions(student=student)

    sol = next(solutions)
    assert len(sol.solution.output) == 0

    with pytest.raises(StopIteration):
        next(solutions)
