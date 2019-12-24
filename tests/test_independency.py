from degreepath.data import course_from_str, Student
from degreepath.area import AreaOfStudy
from degreepath.context import RequirementContext
from typing import Any


def test_overlaps(caplog: Any) -> None:
    transcript = [course_from_str(c) for c in ["MUSIC 212", "MUSIC 214", "MUSIC 301", "MUSIC 302"]]
    s = Student.load({'courses': transcript})

    area = AreaOfStudy.load(student=s, specification={
        "result": {"all": [
            {"requirement": "Core"},
            {"requirement": "Electives"},
        ]},
        "requirements": {
            "Core": {
                "result": {"all": [
                    {"course": "MUSIC 212"},
                    {"course": "MUSIC 214"},
                ]},
            },
            "Electives": {
                "result": {
                    "from": "courses",
                    "where": {
                        "$and": [
                            {"subject": {"$eq": "MUSIC"}},
                            {"level": {"$eq": [300]}},
                        ],
                    },
                    "all": [
                        {"assert": {"count(courses)": {"$gte": 2}}},
                    ],
                },
            },
        },
    })

    ctx = RequirementContext(student=s)

    area.result.find_independent_children(items=area.result.items, ctx=ctx)

    solutions = list(area.solutions(student=s))
    assert len(solutions) == 1

    result = solutions[0].audit()

    assert result.ok() is True


def x_test_overlaps(caplog: Any) -> None:
    transcript = [course_from_str(c) for c in [
        "MUSIC 212", "MUSIC 214", "MUSIC 237", "MUSIC 251", "MUSIC 252", "MUSIC 298",
        "MUSIC 222", "MUSIC 224", "MUSIC 247", "MUSIC 261", "MUSIC 262", "MUSIC 299", "MUSIC 301", "MUSIC 302",
        "MUSPF 101", "MUSPF 102", "MUSPF 103", "MUSPF 104", "MUSPF 105", "MUSPF 106",
    ]]

    s = Student.load({'courses': transcript})

    area = AreaOfStudy.load(student=s, specification={
        "result": {"all": [
            {"requirement": "Core"},
            {"requirement": "Electives"},
            {"requirement": "Lessons"},
        ]},
        "requirements": {
            "Core": {
                "result": {"all": [
                    {"course": "MUSIC 212"},
                    {"course": "MUSIC 214"},
                    {"course": "MUSIC 237"},
                    {"course": "MUSIC 251"},
                    {"course": "MUSIC 261"},
                    {"course": "MUSIC 298"},
                ]},
            },
            "Electives": {
                "result": {
                    "from": "courses",
                    "where": {
                        "$and": [
                            {"subject": {"$eq": "MUSIC"}},
                            {"level": {"$in": [200, 300]}},
                        ],
                    },
                    "all": [
                        {"assert": {"count(courses)": {"$gte": 8}}},
                        {
                            "where": {"level": {"$eq": 300}},
                            "assert": {"count(courses)": {"$gte": 2}},
                        },
                    ],
                },
            },
            "Lessons": {
                "result": {
                    "from": "courses",
                    "where": {"subject": {"$eq": "MUSPF"}},
                    "all": [
                        {"assert": {"count(terms)": {"$gte": 6}}},
                        {"assert": {"sum(credits)": {"$gte": 2.5}}},
                        {
                            "where": {"credits": {"$eq": 0.5}},
                            "assert": {"count(terms)": {"$gte": 4}},
                        },
                    ],
                },
            },
        },
    })

    solutions = list(area.solutions(student=s))
    assert len(solutions) == 1

    result = solutions[0].audit()

    assert result.ok() is True
