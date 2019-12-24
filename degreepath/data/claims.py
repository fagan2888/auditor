import attr
from typing import List, Optional, Tuple, Dict
from collections import defaultdict
import logging

from ..claim import ClaimAttempt, Claim
from .course import CourseInstance

logger = logging.getLogger(__name__)
debug: Optional[bool] = None


@attr.s(slots=True, kw_only=True, frozen=False, auto_attribs=True)
class CourseClaims:
    """Make claims against courses, to ensure that they are only used once
    (with exceptions) in an audit."""

    claims: Dict[str, List[Claim]] = attr.ib(factory=lambda: defaultdict(list))

    # A multicountable set describes the ways in which a course may be
    # counted. If no multicountable set describes the course, it may only be
    # counted once.
    multicountable: Dict[str, List[Tuple[str, ...]]] = attr.ib(factory=dict)

    def with_empty_claims(self) -> 'CourseClaims':
        return attr.evolve(self, claims=defaultdict(list))

    def merge_claims(self, *claims: 'CourseClaims') -> 'CourseClaims':
        merged_claims_dict = self.claims

        for claimset in claims:
            merged_claims_dict.update(claimset.claims)

        return attr.evolve(self, claims=merged_claims_dict)

    def make_claim(self, *, course: CourseInstance, path: Tuple[str, ...], allow_claimed: bool = False) -> ClaimAttempt:
        # This function is called often enough that we want to avoid even
        # calling the `logging` module unless we're actually logging things.
        # (On a 90-second audit, this saved nearly 30 seconds.)
        global debug
        if debug is None:
            debug = __debug__ and logger.isEnabledFor(logging.DEBUG)

        path_reqs_only = tuple(r for r in path if r[0] == '%')

        # build a claim so it can be returned later
        claim = Claim(course=course, claimant_path=path, claimant_requirements=path_reqs_only)

        # If the claimant is a CourseRule specified with the `.allow_claimed`
        # option, the claim succeeds (and is not recorded).
        if allow_claimed:
            if debug: logger.debug('claim for clbid=%s allowed due to rule having allow_claimed', course.clbid)
            return ClaimAttempt(claim, conflict_with=tuple(), failed=False)

        # If there are no prior claims, the claim is automatically allowed.
        prior_claims = self.claims[course.clbid]
        if not prior_claims:
            if debug: logger.debug('no prior claims for clbid=%s', course.clbid)
            self.claims[course.clbid].append(claim)
            return ClaimAttempt(claim, conflict_with=tuple(), failed=False)

        # See if there are any multicountable sets that apply to this course
        if course.course() in self.multicountable:
            return self.make_multicountable_claim(claim=claim, course=course, path=path)

        # If there are no applicable multicountable sets, return a claim
        # attempt against the prior claims.
        if prior_claims:
            if debug: logger.debug('no multicountable reqpaths for clbid=%s; the claim conflicts with %s', course.clbid, prior_claims)
            return ClaimAttempt(claim, conflict_with=tuple(prior_claims), failed=True)

        # If there are no prior claims, it is automatically successful.
        if debug: logger.debug('no multicountable reqpaths for clbid=%s; the claim has no conflicts', course.clbid)
        self.claims[course.clbid].append(claim)
        return ClaimAttempt(claim, conflict_with=tuple(), failed=False)

    def make_multicountable_claim(self, *, claim: Claim, course: CourseInstance, path: Tuple[str, ...]) -> ClaimAttempt:
        """
        We can allow a course to be claimed by multiple requirements, if
        that's what is required by the specification.

        A `multicountable` attribute is a dictionary of {DEPTNUM: List[RequirementPath]}.
        That is, it looks like the following:

        multicountable: [
           "DEPT 123": [
                ["Requirement Name"],
                ["A", "Nested", "Requirement"],
           ],
        }

        where each of the RequirementPath is a list of strings that match up
        to a requirement defined somewhere in the file.
        """

        path_reqs_only = tuple(r for r in path if r[0] == '%')
        prior_claims = self.claims[course.clbid]

        # Find any multicountable sets that may apply to this course
        applicable_reqpaths: List[Tuple[str, ...]] = self.multicountable.get(course.course(), [])

        prior_claimers = list(set(cl.claimant_requirements for cl in prior_claims))

        if debug: logger.debug('applicable reqpaths: %s', applicable_reqpaths)

        applicable_reqpath_set = None

        for reqpath in applicable_reqpaths:
            if debug: logger.debug('checking reqpath %s', reqpath)

            if reqpath == path_reqs_only:
                if debug: logger.debug('done checking reqpaths')
                applicable_reqpath_set = reqpath
                break

            if debug: logger.debug('done checking reqpath %s; ', reqpath)

        if applicable_reqpath_set is None:
            if prior_claims:
                if debug: logger.debug('no applicable multicountable reqpath was found for clbid=%s; the claim conflicts with %s', course.clbid, prior_claims)
                return ClaimAttempt(claim, conflict_with=tuple(prior_claims), failed=True)
            else:
                if debug: logger.debug('no applicable multicountable reqpath was found for clbid=%s; the claim has no conflicts', course.clbid)
                self.claims[course.clbid].append(claim)
                return ClaimAttempt(claim, conflict_with=tuple(), failed=False)

        # limit to just the clauses in the reqpath which have not been used
        available_reqpaths = [
            reqpath
            for reqpath in applicable_reqpath_set
            if reqpath not in prior_claimers
        ]

        if not available_reqpaths:
            if debug: logger.debug('there was an applicable multicountable reqpath for clbid=%s; however, all of the clauses have already been matched', course.clbid)
            if prior_claims:
                return ClaimAttempt(claim, conflict_with=tuple(prior_claims), failed=True)
            else:
                self.claims[course.clbid].append(claim)
                return ClaimAttempt(claim, conflict_with=tuple(), failed=False)

        if debug: logger.debug('there was an applicable multicountable reqpath for clbid=%s: %s', course.clbid, available_reqpaths)
        self.claims[course.clbid].append(claim)
        return ClaimAttempt(claim, conflict_with=tuple(), failed=False)
