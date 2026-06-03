from pydantic import BaseModel


class DesignSpec(BaseModel):
    class_name: str
    description: str
    attributes: list[dict]  # [{"name": "...", "type": "...", "description": "..."}]
    methods: list[dict]  # [{"name": "...", "signature": "...", "description": "..."}]
    notes: list[str]


class TestReport(BaseModel):
    passed: bool
    summary: str
    failed_tests: list[dict]  # [{"test_name": "...", "reason": "..."}]
    missing_features: list[str]


class DevResult(BaseModel):
    status: str
    file_written: str
