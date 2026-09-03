{
  "commands": [
    "export SKIP_VALIDATION=True DS_TAG=${ds_tag} NGIAB_TAG=${ngiab_tag} && /root/datastreamcli/scripts/datastream -s DAILY -n ${nprocs} -F s3://${s3_bucket}/forcings/v2.2_hydrofabric/ngen.DAILY/forcing_${run_type_l}/${init}/ngen.t${init}z.${run_type_l}.forcing.${fcst}.VPU_${vpu}.nc --FORCING_SOURCE NWM_V3_${run_type_h}_${init}${member_suffix} -d /root/outputs -N s3://${s3_bucket}/resources/v2.2_hydrofabric/bmi_configs/cfe_nom_fixed/VPU_${vpu}/ngen-bmi-configs.tar.gz -g s3://${s3_bucket}/resources/v2.2_hydrofabric/geopackages/VPU_${vpu}/nextgen_VPU_${vpu}.gpkg -R https://${s3_bucket}.s3.amazonaws.com/realizations/cfe_nom/realization_VPU_${vpu}.json --S3_BUCKET ${s3_bucket} --S3_PREFIX test/nextstream/outputs/cfe_nom/v2.2_hydrofabric/ngen.DAILY/${run_type_l}/${init}${member_path}/VPU_${vpu}"
  ]
}
