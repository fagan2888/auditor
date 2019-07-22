from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, TYPE_CHECKING
import itertools
import logging

from .source import FromInput
from .assertion import AnyAssertion, load_assertion
from ...limit import LimitSet, Limit
from ...clause import Clause, str_clause, load_clause
from ...solution import FromSolution
from ...constants import Constants


@dataclass(frozen=True)
class FromRule:
    source: FromInput
    action: Optional[Clause]
    limit: LimitSet
    where: Optional[Clause]
    allow_claimed: bool

    def to_dict(self):
        return {
            "type": "from",
            "source": self.source.to_dict(),
            "limit": self.limit.to_dict(),
            "action": self.action.to_dict() if self.action else None,
            "where": self.where.to_dict() if self.where else None,
            "allow_claimed": self.allow_claimed,
            "status": "skip",
            "state": self.state(),
            "ok": self.ok(),
            "rank": self.rank(),
        }

    def state(self):
        return "rule"

    def ok(self):
        return True

    def rank(self):
        return 0

    @staticmethod
    def can_load(data: Dict) -> bool:
        if "from" in data:
            return True
        return False

    @staticmethod
    def load(data: Dict, c: Constants):
        where = data.get("where", None)
        if where is not None:
            where = load_clause(where, c)

        limit = LimitSet.load(data=data.get("limit", None))

        action = None
        if "assert" in data:
            action = load_clause(data["assert"], c)

        allow_claimed = data.get('allow_claimed', False)

        return FromRule(
            source=FromInput.load(data["from"], c),
            action=action,
            limit=limit,
            where=where,
            allow_claimed=allow_claimed,
        )

    def validate(self, *, ctx):
        self.source.validate(ctx=ctx)
        if self.action:
            self.action.validate(ctx=ctx)

    def solutions_when_student(self, *, ctx, path):
        if self.source.itemtype == "courses":
            data = ctx.transcript

            if self.source.repeat_mode == "first":
                filtered_courses = []
                course_identities = set()
                for course in data:
                    if course.identity not in course_identities:
                        filtered_courses.append(course)
                        course_identities.add(course.identity)
                data = filtered_courses
        else:
            raise KeyError(f"{self.source.itemtype} not yet implemented")

        yield data

    def solutions_when_saves(self, *, ctx, path):
        saves = [
            ctx.save_rules[s].solutions(ctx=ctx, path=path)
            for s in self.source.saves
        ]

        for p in itertools.product(*saves):
            data = set(item for save_result in p for item in save_result.stored())
            yield data

    def solutions_when_reqs(self, *, ctx, path):
        reqs = [
            ctx.requirements[s].solutions(ctx=ctx, path=path)
            for s in self.source.requirements
        ]

        for p in itertools.product(*reqs):
            data = set(item for req_result in p for item in req_result.matched())
            yield data

    def solutions(self, *, ctx, path: List[str]):
        path = [*path, f".from"]
        logging.debug(f"{path}")

        if self.source.mode == "student":
            iterable = self.solutions_when_student(ctx=ctx, path=path)
        elif self.source.mode == "saves":
            iterable = self.solutions_when_saves(ctx=ctx, path=path)
        elif self.source.mode == "requirements":
            iterable = self.solutions_when_reqs(ctx=ctx, path=path)
        else:
            raise KeyError(f'unknown "from" type "{self.source.mode}"')

        assert self.action is not None

        did_iter = False
        for data in iterable:
            if self.where is not None:
                logging.debug(f"fromrule/filter/clause: {str_clause(self.where)}")
                if data:
                    for i, c in enumerate(data):
                        logging.debug(f"fromrule/filter/before/{i}: {c}")
                else:
                    logging.debug(f"fromrule/filter/before: []")

                data = [c for c in data if c.apply_clause(self.where)]

                if data:
                    for i, c in enumerate(data):
                        logging.debug(f"fromrule/filter/after/{i}: {c}")
                else:
                    logging.debug(f"fromrule/filter/after: []")

            for course_set in self.limit.limited_transcripts(data):
                # for n in self.action.range(items=course_set):
                #     for combo in itertools.combinations(course_set, n):
                #         logging.debug(f"fromrule/combo/size={n} of {len(course_set)} :: {[str(c) for c in combo]}")
                #         did_iter = True
                #         yield FromSolution(output=combo, rule=self)

                # for combo in itertools.combinations(course_set, n):
                #     logging.debug(f"fromrule/combo/size={n} of {len(course_set)} :: {[str(c) for c in combo]}")
                #     did_iter = True
                #     yield FromSolution(output=combo, rule=self)

                # also yield one with the entire set of courses
                yield FromSolution(output=course_set, rule=self)

        if not did_iter:
            # be sure we always yield something
            logging.info("did not yield anything; yielding empty collection")
            yield FromSolution(output=[], rule=self)
