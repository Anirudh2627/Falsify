"""Tests for LLM JSON extraction/repair utilities."""

from __future__ import annotations

import pytest

from app.falsify.exceptions import MalformedLLMResponseError
from app.falsify.llm.json_utils import extract_json


class TestExtractJson:
    def test_direct_json(self):
        assert extract_json('{"a": 1}') == {"a": 1}

    def test_fenced_json(self):
        raw = "Here is the answer:\n```json\n{\"supports_claim\": true}\n```\nHope that helps!"
        assert extract_json(raw) == {"supports_claim": True}

    def test_json_embedded_in_prose(self):
        raw = 'Sure! The assessment is {"contradicts_claim": false, "relevance_score": 0.8} as requested.'
        assert extract_json(raw)["relevance_score"] == 0.8

    def test_trailing_comma_repaired(self):
        raw = '{"items": [1, 2, 3,], "ok": true,}'
        assert extract_json(raw) == {"items": [1, 2, 3], "ok": True}

    def test_json_array(self):
        assert extract_json("[1, 2, 3]") == [1, 2, 3]

    def test_nested_braces_in_strings(self):
        raw = '{"reasoning": "the text contains {braces} and }", "ok": true}'
        assert extract_json(raw)["ok"] is True

    def test_garbage_raises(self):
        with pytest.raises(MalformedLLMResponseError):
            extract_json("no json here at all")

    def test_empty_raises(self):
        with pytest.raises(MalformedLLMResponseError):
            extract_json("   ")

    def test_none_raises(self):
        with pytest.raises(MalformedLLMResponseError):
            extract_json(None)
