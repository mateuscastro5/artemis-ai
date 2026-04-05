from enum import Enum


class DifficultyLabel(str, Enum):
    TRIVIAL = "trivial"
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    EXPERT = "expert"


class ChangeType(str, Enum):
    BUGFIX = "bugfix"
    FEATURE = "feature"
    REFACTOR = "refactor"
    CONFIG = "config"
    DOCS = "docs"
    TEST = "test"


class AnalysisStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CORRECTED = "corrected"
    DOUBTFUL = "doubtful"


class ExampleOrigin(str, Enum):
    GOLD_SET = "gold_set"
    USER_FEEDBACK = "user_feedback"
    AUTO_CONFIRMED = "auto_confirmed"
