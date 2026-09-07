"""Regulatory Dataset Integrity & Schema Tests.

Validates the canonical regulatory dataset (frontend/src/data/question_regulatory_map.json):
  1. Exactly 84 question entries (keys "1" through "84").
  2. Complete schema coverage (topic, primary, secondary, ipc, ipc_short, criminal, criminal_short, civil, consequence, severity).
  3. Strict enum constraint on severity ("high", "medium", "low").
  4. Concise summaries for UI rendering (ipc_short, criminal_short).
  5. Critical hazard alignment (major fire, electrical, and gas questions categorized as high severity).
  6. Injection safety (no raw HTML tags or unescaped executable blocks in text).
"""
import json
import re
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_FILE = REPO_ROOT / "frontend" / "src" / "data" / "question_regulatory_map.json"
QUESTIONS_FILE = REPO_ROOT / "backend" / "questions.json"


@pytest.fixture(scope="module")
def regulatory_data():
    assert DATA_FILE.exists(), f"Regulatory map file missing: {DATA_FILE}"
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def canonical_questions():
    assert QUESTIONS_FILE.exists(), f"Questions file missing: {QUESTIONS_FILE}"
    with open(QUESTIONS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


class TestRegulatoryDataSchema:
    """Verify JSON structure, 84-question count, and schema conformity."""

    def test_top_level_metadata_exists(self, regulatory_data):
        assert "questions" in regulatory_data
        assert isinstance(regulatory_data["questions"], dict)
        assert "version" in regulatory_data
        assert "source" in regulatory_data
        assert "status" in regulatory_data
        assert regulatory_data["status"].startswith("UNVERIFIED") or regulatory_data["status"] == "VERIFIED"

    def test_exactly_84_questions_present(self, regulatory_data):
        questions = regulatory_data["questions"]
        assert len(questions) == 84
        for qid in range(1, 85):
            assert str(qid) in questions, f"Question ID {qid} missing from regulatory map"

    def test_required_fields_presence_and_types(self, regulatory_data):
        required_fields = [
            "topic",
            "primary",
            "secondary",
            "ipc",
            "ipc_short",
            "criminal",
            "criminal_short",
            "civil",
            "consequence",
            "severity",
        ]
        questions = regulatory_data["questions"]
        for qid_str, item in questions.items():
            assert isinstance(item, dict), f"Question {qid_str} entry must be a dictionary"
            for field in required_fields:
                assert field in item, f"Question {qid_str} missing required field '{field}'"
                assert isinstance(item[field], str), f"Question {qid_str} field '{field}' must be a string"
                if field != "secondary":  # secondary can be empty if no secondary statute applies
                    assert len(item[field].strip()) > 0, f"Question {qid_str} field '{field}' cannot be blank"

    def test_severity_values_are_valid_enum(self, regulatory_data):
        allowed_severities = {"high", "medium", "low"}
        questions = regulatory_data["questions"]
        for qid_str, item in questions.items():
            sev = item["severity"]
            assert sev in allowed_severities, f"Question {qid_str} has invalid severity '{sev}'"

    def test_short_fields_are_concise_for_ui(self, regulatory_data):
        questions = regulatory_data["questions"]
        for qid_str, item in questions.items():
            assert len(item["ipc_short"]) <= 150, f"Question {qid_str} ipc_short too long: {len(item['ipc_short'])} chars"
            assert len(item["criminal_short"]) <= 80, f"Question {qid_str} criminal_short too long: {len(item['criminal_short'])} chars"

    def test_no_raw_html_tags(self, regulatory_data):
        html_pattern = re.compile(r"<[a-zA-Z/][^>]*>")
        questions = regulatory_data["questions"]
        for qid_str, item in questions.items():
            for field, val in item.items():
                assert not html_pattern.search(val), f"Question {qid_str} field '{field}' contains raw HTML: {val}"


class TestRegulatoryDomainIntegrity:
    """Verify critical safety hazards and domain mapping."""

    def test_critical_hazards_are_high_severity(self, regulatory_data):
        questions = regulatory_data["questions"]
        # ANSUL (Q13), Kaçak Akım Rölesi (Q21), Hasarlı Kablo (Q26), LPG/Gaz Tüpleri (Q78)
        assert questions["13"]["severity"] == "high", "Q13 (ANSUL) must be high severity"
        assert questions["21"]["severity"] == "high", "Q21 (Kaçak Akım) must be high severity"
        assert questions["26"]["severity"] == "high", "Q26 (Hasarlı Kablo) must be high severity"
        assert questions["78"]["severity"] == "high", "Q78 (Gaz Tüpleri) must be high severity"

    def test_question_id_alignment_with_questions_json(self, regulatory_data, canonical_questions):
        assert len(canonical_questions) == 84
        for q in canonical_questions:
            qid_str = str(q["id"])
            assert qid_str in regulatory_data["questions"]
