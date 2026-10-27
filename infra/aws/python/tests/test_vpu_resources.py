from research_datastream.vpu_resources import resources, settings

MAIN_TF = """
locals {
  vpu_resource_overrides = {
    # "16" = {
    #   geopackage = "commented/out.gpkg"
    # }
    "17" = {
      bmi_configs = "resources/bmi/cfe_nom/contributions/423/VPU_17/ngen-bmi-configs.tar.gz"
    }
  }
  vpu_resources = {
    for vpu in var.all_vpus : vpu => merge({
      geopackage  = "resources/geopackages/VPU_${vpu}/nextgen_VPU_${vpu}.gpkg"
      bmi_configs = "resources/bmi/cfe_nom_fixed/VPU_${vpu}/ngen-bmi-configs.tar.gz"
    }, try(local.vpu_resource_overrides[vpu], {}))
  }
}
"""


def test_resources_default():
    assert resources("cfe-nom", "16", MAIN_TF) == {
        "geopackage": "resources/geopackages/VPU_16/nextgen_VPU_16.gpkg",
        "bmi_configs": "resources/bmi/cfe_nom_fixed/VPU_16/ngen-bmi-configs.tar.gz",
    }


def test_resources_override_merges_over_default():
    found = resources("cfe-nom", "17", MAIN_TF)
    assert found["geopackage"] == "resources/geopackages/VPU_17/nextgen_VPU_17.gpkg"
    assert found["bmi_configs"] == "resources/bmi/cfe_nom/contributions/423/VPU_17/ngen-bmi-configs.tar.gz"


def test_resources_real_main_tf():
    assert set(resources("routing-only", "01")) == {"geopackage"}
    assert set(resources("lstm_0", "01")) == {"geopackage", "bmi_configs"}


def test_settings():
    tpl = ("runuser -l ec2-user -c 'export DS_TAG=1.7.1 && export NGIAB_TAG=1.6.0 && datastream "
           "-R https://${s3_bucket}.s3.amazonaws.com/realizations/cfe_nom/realization_VPU_${vpu}.json -n 3'")
    assert settings("cfe-nom", tpl) == {
        "ds_tag": "1.7.1",
        "realization": "https://ciroh-community-ngen-datastream.s3.amazonaws.com/realizations/cfe_nom/realization_VPU_${vpu}.json",
    }
