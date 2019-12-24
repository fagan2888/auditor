from degreepath import AreaOfStudy, AreaPointer, Student
from degreepath.audit import audit
from degreepath.data.course import course_from_str
from degreepath.data.area_enums import AreaStatus, AreaType


def test_audit__double_history_and_studio():
    student = Student.load({
        'areas': [
            AreaPointer(
                code='140',
                status=AreaStatus.Declared,
                kind=AreaType.Major,
                name='Studio Art',
                degree='B.A.',
                dept='ART',
                gpa=None,
            ),
            AreaPointer(
                code='135',
                status=AreaStatus.Declared,
                kind=AreaType.Major,
                name='Art History',
                degree='B.A.',
                dept='ART',
                gpa=None,
            ),
        ],
        'courses': [
            course_from_str('DEPT 123'),
        ],
    })

    area = AreaOfStudy.load(student=student, specification={
        'name': 'Art History Test',
        'type': 'major',
        'code': '140',
        'degree': 'B.A.',

        'result': {
            'all': [{'course': 'DEPT 123'}],
        }
    })

    messages = list(audit(area=area, student=student))
    result = messages[-1].result

    assert result.result.items[-1].result.items[-1].result.assertions[0].assertion.expected == 18


def test_audit__single_studio_art():
    student = Student.load({
        'areas': [
            AreaPointer(
                code='140',
                status=AreaStatus.Declared,
                kind=AreaType.Major,
                name='Studio Art',
                degree='B.A.',
                dept='ART',
                gpa=None,
            ),
        ],
        'courses': [
            course_from_str('DEPT 123'),
        ],
    })

    area = AreaOfStudy.load(student=student, specification={
        'name': 'Art History Test',
        'type': 'major',
        'code': '140',
        'degree': 'B.A.',

        'result': {
            'all': [{'course': 'DEPT 123'}],
        }
    })

    messages = list(audit(area=area, student=student))
    result = messages[-1].result

    assert result.result.items[-1].result.items[-1].result.assertions[0].assertion.expected == 21


def test_audit__single_art_history():
    student = Student.load({
        'areas': [
            AreaPointer(
                code='135',
                status=AreaStatus.Declared,
                kind=AreaType.Major,
                name='Art History',
                degree='B.A.',
                dept='ART',
                gpa=None,
            ),
        ],
        'courses': [
            course_from_str('DEPT 123'),
        ],
    })

    area = AreaOfStudy.load(student=student, specification={
        'name': 'Art History Test',
        'type': 'major',
        'code': '135',
        'degree': 'B.A.',

        'result': {
            'all': [{'course': 'DEPT 123'}],
        }
    })

    messages = list(audit(area=area, student=student))
    result = messages[-1].result

    assert result.result.items[-1].result.items[-1].result.assertions[0].assertion.expected == 21


def test_audit__double_art_history_and_other():
    student = Student.load({
        'areas': [
            AreaPointer(
                code='135',
                status=AreaStatus.Declared,
                kind=AreaType.Major,
                name='Art History',
                degree='B.A.',
                dept='ART',
                gpa=None,
            ),
            AreaPointer(
                code='001',
                status=AreaStatus.Declared,
                kind=AreaType.Major,
                name='Other',
                degree='B.A.',
                dept='DEPT',
                gpa=None,
            ),
        ],
        'courses': [
            course_from_str('DEPT 123'),
        ],
    })

    area = AreaOfStudy.load(student=student, specification={
        'name': 'Art History',
        'type': 'major',
        'code': '135',
        'degree': 'B.A.',

        'result': {
            'all': [{'course': 'DEPT 123'}],
        }
    })

    messages = list(audit(area=area, student=student))
    result = messages[-1].result

    assert result.result.items[-1].result.items[-1].result.assertions[0].assertion.expected == 21


def test_audit__triple_arts_and_other():
    student = Student.load({
        'areas': [
            AreaPointer(
                code='135',
                status=AreaStatus.Declared,
                kind=AreaType.Major,
                name='Art History',
                degree='B.A.',
                dept='ART',
                gpa=None,
            ),
            AreaPointer(
                code='140',
                status=AreaStatus.Declared,
                kind=AreaType.Major,
                name='Studio Art',
                degree='B.A.',
                dept='ART',
                gpa=None,
            ),
            AreaPointer(
                code='001',
                status=AreaStatus.Declared,
                kind=AreaType.Major,
                name='Other',
                degree='B.A.',
                dept='DEPT',
                gpa=None,
            ),
        ],
        'courses': [
            course_from_str('DEPT 123'),
        ],
    })

    area = AreaOfStudy.load(student=student, specification={
        'name': 'Art History Test',
        'type': 'major',
        'code': '001',
        'degree': 'B.A.',

        'result': {
            'all': [{'course': 'DEPT 123'}],
        }
    })

    messages = list(audit(area=area, student=student))
    result = messages[-1].result

    assert result.result.items[-1].result.items[-1].result.assertions[0].assertion.expected == 21

    area = AreaOfStudy.load(student=student, specification={
        'name': 'Art History',
        'type': 'major',
        'code': '135',
        'degree': 'B.A.',

        'result': {
            'all': [{'course': 'DEPT 123'}],
        }
    })

    messages = list(audit(area=area, student=student))
    result = messages[-1].result

    assert result.result.items[-1].result.items[-1].result.assertions[0].assertion.expected == 18

    area = AreaOfStudy.load(student=student, specification={
        'name': 'Studio Art',
        'type': 'major',
        'code': '140',
        'degree': 'B.A.',

        'result': {
            'all': [{'course': 'DEPT 123'}],
        }
    })

    messages = list(audit(area=area, student=student))
    result = messages[-1].result

    assert result.result.items[-1].result.items[-1].result.assertions[0].assertion.expected == 18
