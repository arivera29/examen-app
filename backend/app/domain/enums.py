from enum import Enum


class QuestionType(str, Enum):
    SINGLE_CHOICE = "single_choice"
    MULTIPLE_CHOICE = "multiple_choice"
    OPEN = "open"
    TRUE_FALSE = "true_false"


class ExamMode(str, Enum):
    SIMULATION = "simulation"
    REAL = "real"


class AttemptPolicy(str, Enum):
    FLEXIBLE = "flexible"
    SEQUENTIAL = "sequential"


class ExamStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    CLOSED = "closed"


class InvitationStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    STARTED = "started"
    COMPLETED = "completed"
    EXPIRED = "expired"


class AttemptStatus(str, Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    TIMED_OUT = "timed_out"


class ProctoringEventType(str, Enum):
    EYE_MOVEMENT = "eye_movement"
    FACIAL_EXPRESSION = "facial_expression"
    MOUSE_ANOMALY = "mouse_anomaly"
    NO_FACE = "no_face"
    MULTIPLE_FACES = "multiple_faces"
    TAB_SWITCH = "tab_switch"


class SnapshotType(str, Enum):
    START = "start"
    PROGRESS = "progress"
