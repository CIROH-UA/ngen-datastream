"""Tests for the shared completion-marker rule (research_datastream_core.outputs)."""

from research_datastream_core import is_datastream_run, output_marker

NGEN = ["runuser -l ec2-user -c '/home/ec2-user/datastreamcli/scripts/datastream -s DAILY "
        "--S3_BUCKET bkt --S3_PREFIX outputs/cfe_nom/ngen.20261019/short_range/06/VPU_01'"]
FORCING = ["runuser -l ec2-user -c 'docker run forcingprocessor ...'",
           "echo --s3_bucket bkt --s3_prefix forcings/ngen.20261019/forcing_short_range/06"]


def test_ngen_run_marker_is_merkdir():
    assert is_datastream_run(NGEN)
    assert output_marker(NGEN) == (
        "bkt", "outputs/cfe_nom/ngen.20261019/short_range/06/VPU_01/merkdir.file")


def test_forcing_marker_is_metadata_csv():
    assert not is_datastream_run(FORCING)
    assert output_marker(FORCING) == (
        "bkt", "forcings/ngen.20261019/forcing_short_range/06/metadata/forcings_metadata/metadata.csv")


def test_no_s3_sink():
    assert output_marker(["/root/datastreamcli/scripts/datastream -s DAILY -d /out"]) is None
