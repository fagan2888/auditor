from typing import Any, Mapping, Optional, List, Iterator, Collection, TYPE_CHECKING
import logging
import attr
import markdown2  # type: ignore

from ..base import Rule, BaseRequirementRule
from ..base.requirement import AuditedBy
from ..constants import Constants
from ..solution.requirement import RequirementSolution
from ..rule.query import QueryRule
from ..solve import find_best_solution

if TYPE_CHECKING:  # pragma: no cover
    from ..context import RequirementContext
    from ..data import Clausable, CourseInstance  # noqa: F401

logger = logging.getLogger(__name__)


@attr.s(cache_hash=True, slots=True, kw_only=True, frozen=True, auto_attribs=True)
class RequirementRule(Rule, BaseRequirementRule):
    result: Optional[Rule]

    @staticmethod
    def can_load(data: Mapping) -> bool:
        return "requirement" in data

    @staticmethod
    def load(data: Mapping[str, Any], *, name: str, c: Constants, path: List[str], ctx: 'RequirementContext') -> Optional['RequirementRule']:
        from ..load_rule import load_rule

        path = [*path, f"%{name}"]

        # "name" is allowed due to emphasis requirements
        allowed_keys = set(['if', 'in_gpa', 'name', 'else', 'then', 'result', 'message', 'contract', 'requirements', 'department_audited', 'department-audited', 'registrar-audited', 'registrar_audited'])
        given_keys = set(data.keys())
        assert given_keys.difference(allowed_keys) == set(), f"expected set {given_keys.difference(allowed_keys)} to be empty (at {path})"

        result = data.get("result", None)

        # be able to exclude requirements if they shouldn't exist
        if 'if' in data:
            assert ctx, TypeError('conditional requirements are only supported at the top-level')

            rule = QueryRule.load(data['if'], c=c, path=[*path, '#if'], ctx=ctx)

            with ctx.fresh_claims():
                s = find_best_solution(rule=rule, ctx=ctx)

            if not s:
                return None

            if 'then' in data and 'else' in data:
                if s.ok():
                    result = data['then']
                else:
                    result = data['else']
            elif ('then' in data and 'else' not in data) or ('then' not in data and 'else' in data):
                raise TypeError(f'{path} in an if:, with one of then: or else:; expected both then: and else:')
            elif s.ok():
                # we support some "Optional" requirements that are department-audited
                result = data.get("result", None)
            else:
                return None

        if result is not None:
            result = load_rule(data=result, c=c, children=data.get("requirements", {}), path=path, ctx=ctx)
            if result is None:
                return None

            all_child_names = set(data.get("requirements", {}).keys())
            used_child_names = set(result.get_requirement_names())
            unused_child_names = all_child_names.difference(used_child_names)
            assert unused_child_names == set(), f"expected {unused_child_names} to be empty"

        audited_by = None
        if data.get("department_audited", data.get("department-audited", False)):
            audited_by = AuditedBy.Department
        elif data.get("registrar_audited", data.get("registrar-audited", False)):
            audited_by = AuditedBy.Registrar

        if 'audit' in data:
            raise TypeError('you probably meant to indent that audit: key into the result: key')

        if not audited_by and not result:
            raise TypeError(f'requirements need either audited_by or result (at {path})')

        message = data.get("message", None)
        if message:
            message = markdown2.markdown(message)

        return RequirementRule(
            name=name,
            message=message,
            result=result,
            is_contract=data.get("contract", False),
            in_gpa=data.get("in_gpa", True),
            audited_by=audited_by,
            path=tuple(path),
        )

    def validate(self, *, ctx: 'RequirementContext') -> None:
        assert isinstance(self.name, str)
        assert self.name.strip() != ""

        if self.message is not None:
            assert isinstance(self.message, str)
            assert self.message.strip() != ""

        if self.result is not None:
            self.result.validate(ctx=ctx)

    def get_requirement_names(self) -> List[str]:
        return [self.name]

    def get_required_courses(self, *, ctx: 'RequirementContext') -> Collection['CourseInstance']:
        if self.result:
            return self.result.get_required_courses(ctx=ctx)
        return tuple()

    def exclude_required_courses(self, to_exclude: Collection['CourseInstance']) -> 'RequirementRule':
        if not self.result:
            return self

        result = self.result.exclude_required_courses(to_exclude)
        return attr.evolve(self, result=result)

    def solutions(self, *, ctx: 'RequirementContext', depth: Optional[int] = None) -> Iterator[RequirementSolution]:
        if ctx.get_waive_exception(self.path):
            logger.debug("forced override on %s", self.path)
            yield RequirementSolution.from_rule(rule=self, solution=self.result, overridden=True)
            return

        logger.debug("%s auditing %s", self.path, self.name)

        if self.audited_by is not None:
            logger.debug("%s requirement \"%s\" is audited %s", self.path, self.name, self.audited_by)

        if not self.result:
            logger.debug("%s requirement \"%s\" does not have a result", self.path, self.name)
            yield RequirementSolution.from_rule(rule=self, solution=None)
            return

        for solution in self.result.solutions(ctx=ctx):
            yield RequirementSolution.from_rule(rule=self, solution=solution)

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

        if self.audited_by is not None:
            return False

        if self.result:
            return self.result.has_potential(ctx=ctx)

        return False

    def all_matches(self, *, ctx: 'RequirementContext') -> Collection['Clausable']:
        if not self.result:
            return []

        return self.result.all_matches(ctx=ctx)
