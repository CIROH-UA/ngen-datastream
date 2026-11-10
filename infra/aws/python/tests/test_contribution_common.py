from research_datastream import contribution_common as common

SHA = "ab" * 32


def test_check_sha256():
    assert common.check_sha256({}, SHA).status == "pass"
    assert common.check_sha256({"sha256": SHA.upper()}, SHA).status == "pass"
    mismatch = common.check_sha256({"sha256": "cd" * 32}, SHA)
    assert mismatch.status == "fail" and SHA in mismatch.detail
    assert common.check_sha256({"sha256": "abc"}, SHA).status == "fail"
    # Unquoted, an all-digit hash would reach here as an int.
    assert common.check_sha256({"sha256": 12}, SHA).status == "fail"
