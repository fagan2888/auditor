from dataclasses import dataclass, field
from typing import Tuple, Union, Set
import logging

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Claim:
    crsid: str
    clbid: str
    claimant_path: Tuple[str, ...]
    value: Union

    def to_dict(self):
        return {
            "crsid": self.crsid,
            "clbid": self.clbid,
            "claimant_path": self.claimant_path,
            "value": self.value.to_dict(),
        }


@dataclass(frozen=True)
class ClaimAttempt:
    claim: Claim
    conflict_with: Set[Claim] = field(default_factory=set)

    def failed(self) -> bool:
        return len(self.conflict_with) > 0

    def to_dict(self):
        return {
            "claim": self.claim.to_dict(),
            "conflict_with": [c.to_dict() for c in self.conflict_with],
        }

    def get_course(self, *, ctx):
        return ctx.find_course_by_clbid(self.claim.clbid)
