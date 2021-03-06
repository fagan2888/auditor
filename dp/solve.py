from typing import Optional, Dict, List, Union, TYPE_CHECKING
from decimal import Decimal
import logging

if TYPE_CHECKING:  # pragma: no cover
    from .claim import Claim  # noqa: F401
    from .base import Result, Rule  # noqa: F401
    from .context import RequirementContext

logger = logging.getLogger(__name__)


def find_best_solution(*, rule: 'Rule', ctx: 'RequirementContext', merge_claims: bool = False) -> Optional['Result']:
    logger.debug('solving rule at %s', rule.path)

    result: Optional['Result'] = None
    rank: Union[int, Decimal] = 0

    claims: Dict[str, List['Claim']] = dict()
    if merge_claims:
        claims = ctx.claims

    with ctx.fresh_claims():
        for s in rule.solutions(ctx=ctx):
            inner_ctx = ctx.with_empty_claims()

            tmp_result = s.audit(ctx=inner_ctx)
            tmp_rank = tmp_result.rank()

            if result is None:
                result, rank = tmp_result, tmp_rank

            if tmp_rank > rank:
                result, rank = tmp_result, tmp_rank

            if tmp_result.ok():
                result, rank = tmp_result, tmp_rank
                break

    if merge_claims and inner_ctx:
        ctx.set_claims({**claims, **inner_ctx.claims})

    return result
