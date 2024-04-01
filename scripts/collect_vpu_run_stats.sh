VPUs=("01" "02" "03N" "03S" "03W" "04" "05" "06" "07" "08" "09" "10L" "10U" "11" "12" "13" "14" "15" "16" "17" "18")

for vpu in "${VPUs[@]}"; do
    key="daily/20240326/VPU_${vpu}/datastream-configs/profile.txt"
    aws s3api get-object --bucket ngen-datastream --key "$key" "./data/profiles_n_confs/profile_${vpu}.txt"

    key="daily/20240326/VPU_${vpu}/datastream-configs/conf_datastream.json"
    aws s3api get-object --bucket ngen-datastream --key "$key" "./data/profiles_n_confs/conf_datastream_${vpu}.json"
    
done
