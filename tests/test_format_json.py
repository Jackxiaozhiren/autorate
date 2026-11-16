"""M5's one freeze round: `verify --format json` adds a presentation, not a
compared field. The human rendering must stay byte-identical, and the JSON
object must carry the very lines the human run printed — the same result
object, rendered twice.

This test does not re-derive numbers. It runs the command the operator runs.
"""
from __future__ import annotations

import json

from autorate.cli import main

ARGV = ["verify", "--protocol", "protocol.json"]


def _run(capsys, *extra):
    rc = main(ARGV + list(extra))
    captured = capsys.readouterr()
    return rc, captured.out, captured.err


def test_human_output_is_byte_identical_with_and_without_the_flag(capsys):
    rc_text, text, err_text = _run(capsys)
    rc_flag, flagged, err_flag = _run(capsys, "--format", "text")
    assert rc_text == rc_flag == 0, (err_text, err_flag)
    assert flagged == text, "explicit text is the same renderer, byte for byte"


def test_json_carries_the_human_lines_and_the_same_exit_code(capsys):
    rc_text, text, _ = _run(capsys)
    rc_json, rendered, err_json = _run(capsys, "--format", "json")
    assert rc_json == rc_text == 0, err_json
    doc = json.loads(rendered)

    lines = text.splitlines()
    claim_lines = [line for line in lines if line.startswith("claim ")]
    protocol_line = next(line for line in lines if line.startswith("protocol: "))
    rederived = next(line for line in lines if line.startswith("re-derived "))
    import re
    denominator = re.match(r"re-derived\s+(\d+ /(\d+))\s+values", rederived)

    ids = [line.split(" ", 2)[1] for line in claim_lines]
    assert [c["id"] for c in doc["claims"]] == ids, \
        "the claim ids are the human lines' ids"
    for line, claim in zip(claim_lines, doc["claims"]):
        assert claim["status"] in line and claim["criterion"] in line, \
            "each claim carries exactly what the human line printed"
    assert doc["protocol"] == protocol_line.split(" ", 2)[1]
    assert doc["protocol_digest"] == protocol_line.split(" ")[2]
    assert doc["re_derived"] == denominator.group(1)
    assert doc["total"] == int(denominator.group(2))
    assert doc["exit_code"] == rc_text


def test_json_reports_failures_without_hiding_them(capsys):
    # The green run has no DRIFT lines; the JSON field exists and is empty
    # rather than omitted, so a consumer can tell "none" from "unknown".
    _rc, _text, _err = _run(capsys)
    rc, rendered, err = _run(capsys, "--format", "json")
    doc = json.loads(rendered)
    assert doc["failures"] == []
    assert doc["mismatches"] == []
    assert rc == 0
