from degreepath.area import AreaOfStudy
from degreepath.data import course_from_str, Student
from degreepath.constants import Constants
import yaml
import io
import logging

c = Constants(matriculation_year=2000)

next_assertion = '\n\n... next assertion ...\n\n'


def test_mc__none(caplog):
    caplog.set_level(logging.DEBUG, logger='degreepath.context')

    course = course_from_str('DEPT 123')
    student = Student.load({'courses': [course]})

    test_data = io.StringIO("""
        result:
            either:
                - requirement: Root
                - requirement: Alt

        requirements:
            Root:
                result:
                    course: DEPT 123

            Alt:
                result:
                    course: DEPT 123
    """)

    area = AreaOfStudy.load(specification=yaml.load(stream=test_data, Loader=yaml.SafeLoader), student=student)
    solutions = area.solutions(student=student)

    results = [s.audit() for s in solutions]
    assert len(results) == 3

    result_a, result_b, result_c = results
    assert result_a.ok() is True
    assert result_b.ok() is True
    assert result_c.ok() is True

    assert list(c.claim.course.course() for c in result_c.claims() if c.failed is False) == [course.course()]

    assert result_c.result.items[0].result.claim_attempt.failed is False
    assert result_c.result.items[1].result.claim_attempt.failed is True


def test_mc__none_2(caplog):
    caplog.set_level(logging.DEBUG, logger='degreepath.context')

    course = course_from_str('DEPT 123')
    student = Student.load({'courses': [course]})

    test_data = io.StringIO("""
        result:
            either:
                - requirement: Root
                - requirement: Alt

        requirements:
            Root:
                result:
                    course: DEPT 123

            Alt:
                result:
                    course: DEPT 123

        multicountable:
            DEPT 123:
                - [Root]
    """)

    area = AreaOfStudy.load(specification=yaml.load(stream=test_data, Loader=yaml.SafeLoader), student=student)
    solutions = area.solutions(student=student)

    results = [s.audit() for s in solutions]
    assert len(results) == 3

    result_a, result_b, result_c = results
    assert result_a.ok() is True
    assert result_b.ok() is True
    assert result_c.ok() is True

    assert list(c.claim.course.course() for c in result_c.claims() if c.failed is False) == [course.course()]

    assert result_c.result.items[0].result.claim_attempt.failed is False
    assert result_c.result.items[1].result.claim_attempt.failed is True


def test_mc__only_course_references(caplog):
    caplog.set_level(logging.DEBUG, logger='degreepath.context')

    course = course_from_str('DEPT 123')
    student = Student.load({'courses': [course]})

    test_data = io.StringIO("""
        result:
            all:
                - requirement: Root
                - requirement: Alt

        requirements:
            Root:
                result:
                    course: DEPT 123

            Alt:
                result:
                    course: DEPT 123

        multicountable:
            DEPT 123:
                - [Root]
                - [Alt]
    """)

    area = AreaOfStudy.load(specification=yaml.load(stream=test_data, Loader=yaml.SafeLoader), student=student)
    solutions = area.solutions(student=student)

    results = [s.audit() for s in solutions]
    assert len(results) == 1

    result_a = results[0]
    assert result_a.ok() is True

    assert list(c.claim.course.course() for c in result_a.claims() if c.failed is False) == [course.course(), course.course()]

    assert result_a.result.items[0].result.claim_attempt.failed is False
    assert result_a.result.items[1].result.claim_attempt.failed is False


def test_mc__only_query_references(caplog):
    caplog.set_level(logging.DEBUG, logger='degreepath.context')

    course = course_from_str('DEPT 123')
    student = Student.load({'courses': [course]})

    test_data = io.StringIO("""
        result:
            all:
                - requirement: Root
                - requirement: Alt

        requirements:
            Root:
                result:
                    from: courses
                    assert: {count(courses): {$gte: 1}}

            Alt:
                result:
                    from: courses
                    assert: {count(courses): {$gte: 1}}

        multicountable:
            DEPT 123:
                - [Root]
                - [Alt]
    """)

    area = AreaOfStudy.load(specification=yaml.load(stream=test_data, Loader=yaml.SafeLoader), student=student)
    solutions = area.solutions(student=student)

    results = [s.audit() for s in solutions]
    assert len(results) == 1

    result_a = results[0]
    assert result_a.ok() is True

    assert list(c.claim.course.course() for c in result_a.claims() if c.failed is False) == [course.course(), course.course()]


def x_test_mc__mixed_course_query_references(caplog):
    caplog.set_level(logging.DEBUG, logger='degreepath.context')

    course = course_from_str('DEPT 123')
    student = Student.load({'courses': [course]})

    test_data = io.StringIO("""
        result:
            all:
                - requirement: Root
                - requirement: Alt

        requirements:
            Root:
                result:
                    course: DEPT 123

            Alt:
                result:
                    from: courses
                    assert: {count(courses): {$gte: 1}}

        multicountable:
            DEPT 123:
                - [Root]
                - [Alt]
    """)

    area = AreaOfStudy.load(specification=yaml.load(stream=test_data, Loader=yaml.SafeLoader), student=student)
    solutions = area.solutions(student=student)

    results = [s.audit() for s in solutions]
    assert len(results) == 1

    result_a = results[0]
    assert result_a.ok() is True

    assert list(c.claim.course.course() for c in result_a.claims() if c.failed is False) == [course.course(), course.course()]
