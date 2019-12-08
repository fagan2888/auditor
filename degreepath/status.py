import enum


@enum.unique
class ResultStatus(enum.Enum):
    Pass = "pass"
    Partial = "partial"
    PendingCurrent = "pending-current"
    PendingRegistered = "pending-registered"
    Problem = "problem"
    NotStarted = "not-started"
