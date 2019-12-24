import traceback
import pathlib
import sqlite3
import json
from typing import Iterator, List, Tuple

import yaml
import csv
import sys
import os

from . import AreaOfStudy, Student
from .audit import audit, NoStudentsMsg, AuditStartMsg, ExceptionMsg, AreaFileNotFoundMsg, Message, Arguments


def run(args: Arguments) -> Iterator[Message]:  # noqa: C901
    file_data = list(args.student_data)

    try:
        if args.db_file:
            conn = sqlite3.connect(args.db_file)

            # the sqlite3 module doesn't support passing in a list automatically,
            # so we generate our own set of :n-params
            param_marks = ','.join(f':{i}' for i, _ in enumerate(args.student_files))
            query = f'''
                SELECT student
                FROM file
                WHERE path IN ({param_marks}) OR stnum IN ({param_marks})
            '''

            with conn:
                for (sqldata,) in conn.execute(query, args.student_files):
                    file_data.append(json.loads(sqldata))

        else:
            for student_file in args.student_files:
                with open(student_file, "r", encoding="utf-8") as infile:
                    file_data.append(json.load(infile))

    except FileNotFoundError as ex:
        yield ExceptionMsg(ex=ex, tb=traceback.format_exc(), stnum=None, area_code=None)
        return

    if not file_data:
        yield NoStudentsMsg()
        return

    area_specs: List[Tuple[dict, str]] = list(args.area_specs)

    for area_file in args.area_files:
        try:
            catalog = pathlib.Path(area_file).parent.stem
            with open(area_file, "r", encoding="utf-8") as infile:
                area_specs.append((yaml.load(stream=infile, Loader=yaml.SafeLoader), catalog))
        except FileNotFoundError:
            yield AreaFileNotFoundMsg(area_file=f"{os.path.dirname(area_file)}/{os.path.basename(area_file)}", stnums=[s['stnum'] for s in file_data])
            return

    for raw_student in file_data:
        stnum = raw_student['stnum']

        if args.transcript_only:
            student = Student.load(raw_student, for_area_code=None)
            writer = csv.writer(sys.stdout)
            writer.writerow(['course', 'name', 'clbid', 'type', 'credits', 'term', 'type', 'grade', 'in_gpa'])

            for c in student.transcript.courses:
                writer.writerow([
                    c.course(), c.name, c.clbid, c.course_type.value, str(c.credits), f"{c.year}-{c.term}",
                    c.sub_type.name, c.grade_code.value, 'Y' if c.is_in_gpa else 'N',
                ])

            return

        if args.gpa_only:
            student = Student.load(raw_student, for_area_code=None)
            writer = csv.writer(sys.stdout)
            writer.writerow(['course', 'grade', 'points'])

            applicable = sorted(student.transcript.gpa_items(), key=lambda c: (c.year, c.term, c.course(), c.clbid))
            for c in applicable:
                writer.writerow([c.course(), c.grade_code.value, str(c.grade_points)])

            writer.writerow(['---', 'gpa:', str(student.transcript.gpa())])
            return

        for area_spec, area_catalog in area_specs:
            area_code = area_spec['code']

            student = Student.load(raw_student, for_area_code=area_code)

            area = AreaOfStudy.load(specification=area_spec, student=student)
            area.validate()

            try:
                yield AuditStartMsg(stnum=stnum, area_code=area_code, area_catalog=area_catalog, student=raw_student)
                yield from audit(args=args, area=area, student=student)
            except Exception as ex:
                yield ExceptionMsg(ex=ex, tb=traceback.format_exc(), stnum=stnum, area_code=area_code)
