{
  "commands": [
    "docker run --rm -v /root/run:/mounted_dir -u $(id -u):$(id -g) -w /mounted_dir/datastream-metadata awiciroh/datastream:1.7.1 python3 /datastreamcli/src/datastreamcli/configure_datastream.py --docker_mount /mounted_dir --start_date DAILY --data_dir /root/run --forcing_source NWM_V3_${run_type_h}_${init}${member_suffix} --forcing_split_vpu ${vpu_list} --hydrofabric_version v2.2 --realization /mounted_dir/realization_sloth_nom_cfe_pet.json --realization_provided /root/run/realization_sloth_nom_cfe_pet.json --nprocs ${nprocs} --s3_bucket ${s3_bucket} --s3_prefix test/nextstream/forcings/v2.2_hydrofabric/ngen.DAILY/forcing_${run_type_l}/${init}",
    "docker run --rm -v /root/run:/mounted_dir -u $(id -u):$(id -g) -w /mounted_dir/datastream-metadata awiciroh/forcingprocessor:2.2.1 python3 /forcingprocessor/src/forcingprocessor/nwm_filenames_generator.py /mounted_dir/datastream-metadata/conf_nwmurl.json",
    "docker run --rm -e AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY -v /root/run:/mounted_dir -u $(id -u):$(id -g) -w /mounted_dir/datastream-metadata awiciroh/forcingprocessor:2.2.1 python3 /forcingprocessor/src/forcingprocessor/processor.py /mounted_dir/datastream-metadata/conf_fp.json",
    "aws s3 cp /root/run/datastream-metadata/conf_nwmurl.json $(cat /root/run/datastream-metadata/conf_fp.json | jq -r '.storage.output_path')/metadata/forcings_metadata/conf_nwmurl.json --no-progress"
  ]
}
