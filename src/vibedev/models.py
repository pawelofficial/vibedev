from pydantic import BaseModel


class ComponentSpec(BaseModel):
    """A single class or function to implement inside a file."""

    name: str
    kind: str  # "class" | "function"
    description: str
    attributes: list[dict]  # classes only; [{"name": "...", "type": "...", "description": "..."}]
    methods: list[dict]  # [{"name": "...", "signature": "...", "description": "..."}]
    notes: list[str]


class FileSpec(BaseModel):
    """One source file: its path, what lives in it, and which siblings it imports."""

    path: str  # relative to OUTPUT_DIR, e.g. "store/cart.py"
    description: str
    components: list[ComponentSpec]
    depends_on: list[str]  # paths of other FileSpecs this file imports from


class ProjectSpec(BaseModel):
    """The whole design: a set of files the developer builds in dependency order."""

    project_name: str
    description: str
    files: list[FileSpec]


class TestReport(BaseModel):
    passed: bool
    summary: str
    failed_tests: list[dict]  # [{"test_name": "...", "reason": "..."}]
    missing_features: list[str]


class DevResult(BaseModel):
    status: str
    file_written: str


class ChallengeReport(BaseModel):
    approved: bool  # True when the spec needs no further changes
    remarks: list[str]  # actionable critiques the lead developer must address
