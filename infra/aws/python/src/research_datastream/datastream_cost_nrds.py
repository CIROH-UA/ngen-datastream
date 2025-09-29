# This script answers the question of much it costs to run the NextGen Research Data Stream (NRDS) for a given amount of time
#
#
#
#
import argparse
import boto3
import json
import pandas as pd
import re
from datetime import datetime, timedelta
from botocore.exceptions import BotoCoreError, ClientError
import os

NCATCHMENTS = {
    "forcing":830353,
    "VPU_01": 20567,
    "VPU_02": 35493,
    "VPU_03N": 31326,
    "VPU_03S": 13911,
    "VPU_03W": 30674,
    "VPU_04": 35894,
    "VPU_05": 51580,
    "VPU_06": 14167,
    "VPU_07": 57595,
    "VPU_08": 32993,
    "VPU_09": 11204,
    "VPU_10L": 55046,
    "VPU_10U": 84367,
    "VPU_11": 63177,
    "VPU_12": 36483,
    "VPU_13": 25470,
    "VPU_14": 32977,
    "VPU_15": 39696,
    "VPU_16": 34401,
    "VPU_17": 81591,
    "VPU_18": 41741
}


RUN_TYPE_TIMESTEPS = {
    "short_range" : 18,
    "medium_range" : 240,
    "analysis_assim_extend" : 28,
}

RUN_TYPE_INITS_PER_DAY = {
    "short_range" : 24,
    "medium_range" : 4, 
    "analysis_assim_extend" : 1,
}

def get_aws_cost(start_date: str, end_date: str, tag_key: str, tag_value: str, granularity="MONTHLY"):
    """
    Retrieve AWS costs filtered by a cost allocation tag within a given date range.

    :param start_date: Start date in YYYY-MM-DD format.
    :param end_date: End date in YYYY-MM-DD format.
    :param tag_key: Cost allocation tag key.
    :param tag_value: Cost allocation tag value.
    :param granularity: Time granularity (DAILY or MONTHLY).
    :return: Total cost as a float.
    """
    client = boto3.client("ce")

    response = client.get_cost_and_usage(
        TimePeriod={"Start": start_date, "End": end_date},
        Granularity=granularity,
        Metrics=["UnblendedCost"],
        Filter={
            "Tags": {
                "Key": f"{tag_key}",  
                "Values": [tag_value]
            }
        }
    )

    total_cost = sum(float(item["Total"]["UnblendedCost"]["Amount"]) for item in response["ResultsByTime"])
    
    return total_cost

def parse_profile_date(profile_content):
    """
    Parses profile.txt and computes durations for each profiling step.

    Args:
        profile_content (str): Content of profile.txt.

    Returns:
        dict: A dictionary with profiling step names as keys and durations (in seconds) as values.
    """

    # Parse start and end times for each step
    for line in profile_content.splitlines():
        match = re.match(r"(\w+)_START: (\d+)", line)
        if match:
            try:
                date = datetime.strptime(match.group(2), "%Y%m%d%H%M%S")
                return date
            except ValueError as ve:
                print(f"Timestamp parsing error in line: '{line}' - {ve}")


def parse_profile_durations(profile_content):
    """
    Parses profile.txt and computes durations for each profiling step.

    Args:
        profile_content (str): Content of profile.txt.

    Returns:
        dict: A dictionary with profiling step names as keys and durations (in seconds) as values.
    """
    timestamps = {}
    durations = {}

    # Parse start and end times for each step
    for line in profile_content.splitlines():
        match = re.match(r"(\w+)_START: (\d+)", line)
        if match:
            step = match.group(1)
            try:
                timestamps[f"{step}_START"] = datetime.strptime(match.group(2), "%Y%m%d%H%M%S")
            except ValueError as ve:
                print(f"Timestamp parsing error in line: '{line}' - {ve}")

        match = re.match(r"(\w+)_END: (\d+)", line)
        if match:
            step = match.group(1)
            try:
                timestamps[f"{step}_END"] = datetime.strptime(match.group(2), "%Y%m%d%H%M%S")
            except ValueError as ve:
                print(f"Timestamp parsing error in line: '{line}' - {ve}")

    # Calculate durations
    for key in timestamps.keys():
        step = re.sub(r'_(START|END)$', '', key)  # Remove _START or _END from the key
        start_key = f"{step}_START"
        end_key = f"{step}_END"
        
        if start_key in timestamps and end_key in timestamps:
            duration = (timestamps[end_key] - timestamps[start_key]).total_seconds()
            durations[step] = duration
        else:
            print(f"Missing start or end timestamp for step: {step}")

    return durations

def fetch_instance_details(instance_type, pricing_client):
    """
    Fetches core count, memory, platform, and cost per hour from AWS for a given instance type.

    Args:
        instance_type (str): The EC2 instance type (e.g., 't4g.2xlarge').
        pricing_client (boto3.client): The AWS Pricing client.

    Returns:
        tuple: (vcpu, memory_gib, platform, cost_per_hour)
    """
    try:
        # Initialize EC2 client for instance details
        ec2_client = boto3.client('ec2', region_name='us-east-1')  # Pricing API is in us-east-1

        # Describe instance types to get vCPU and memory
        response = ec2_client.describe_instance_types(InstanceTypes=[instance_type])
        instance = response['InstanceTypes'][0]
        vcpu = instance['VCpuInfo']['DefaultVCpus']
        memory_mib = instance['MemoryInfo']['SizeInMiB']
        memory_gib = memory_mib / 1024  # Convert MiB to GiB
        platform = 'arm' if instance['ProcessorInfo']['SupportedArchitectures'] == ['arm64'] else 'x86'

        # Fetch instance cost using Pricing API
        cost_per_hour = get_instance_cost(instance_type, pricing_client)

        return vcpu, memory_gib, platform, cost_per_hour

    except (BotoCoreError, ClientError) as e:
        print(f"Error fetching details for instance type {instance_type}: {e}")
        return None, None, "Unknown", 0.0

def get_instance_cost(instance_type, pricing_client, region='US East (N. Virginia)'):
    """
    Fetches real-time instance pricing using AWS Pricing API.

    Args:
        instance_type (str): The EC2 instance type.
        pricing_client (boto3.client): The AWS Pricing client.
        region (str): The AWS region name as per AWS Pricing API (e.g., 'US East (N. Virginia)').

    Returns:
        float: Cost per hour in USD.
    """
    try:
        # Define filters for the instance type
        filters = [
            {'Type': 'TERM_MATCH', 'Field': 'instanceType', 'Value': instance_type},
            {'Type': 'TERM_MATCH', 'Field': 'location', 'Value': region},
            {'Type': 'TERM_MATCH', 'Field': 'preInstalledSw', 'Value': 'NA'},
            {'Type': 'TERM_MATCH', 'Field': 'operatingSystem', 'Value': 'Linux'},
            {'Type': 'TERM_MATCH', 'Field': 'tenancy', 'Value': 'Shared'},
            {'Type': 'TERM_MATCH', 'Field': 'capacitystatus', 'Value': 'Used'}
        ]

        # Query AWS Pricing API
        response = pricing_client.get_products(
            ServiceCode='AmazonEC2',
            Filters=filters,
            MaxResults=1
        )

        # Parse price from the response
        price_list = response.get('PriceList', [])
        if not price_list:
            print(f"No pricing information found for instance type: {instance_type}")
            return 0.0

        price_item = json.loads(price_list[0])
        terms = price_item.get('terms', {}).get('OnDemand', {})
        for term_key, term_value in terms.items():
            price_dimensions = term_value.get('priceDimensions', {})
            for dim_key, dim_value in price_dimensions.items():
                price_per_unit = dim_value.get('pricePerUnit', {}).get('USD')
                if price_per_unit:
                    return float(price_per_unit)

        print(f"Could not find price per unit for instance type: {instance_type}")
        return 0.0

    except (BotoCoreError, ClientError) as e:
        print(f"Error fetching pricing for instance type {instance_type}: {e}")
        return 0.0

def build_dataframe_from_files(file_contents, selected_vpus=None):
    """
    Builds a pandas DataFrame from parsed S3 file contents.

    Args:
        file_contents (dict): Dictionary of file contents grouped by file type and keys (e.g., VPU_02).
        selected_vpus (list): List of selected VPUs to include. If None, include all.

    Returns:
        pd.DataFrame: DataFrame with execution details and profiling step durations.
    """
    rows = []

    # Initialize AWS Pricing client
    pricing_client = boto3.client('pricing', region_name='us-east-1')

    # Iterate over execution.json files
    for vpu_key, execution_data in file_contents.get("execution.json", {}).items():
        if vpu_key == "VPU_16":
            pass
        if selected_vpus and vpu_key not in selected_vpus and vpu_key != "forcing":
            continue
        ii_forcing = False
        profile_data = file_contents.get("profile.txt", {}).get(vpu_key)
        if profile_data is None:
            ii_forcing = True
            profile_data = file_contents.get("profile_fp.txt", {}).get("forcing")        

        if ii_forcing:
            domain = "conus"
        else:
            domain = vpu_key

        row = {
            "Domain": domain,  # Extracted key (e.g., VPU_02)
        }

        ncatch = NCATCHMENTS.get(vpu_key, 0)
        row['Number of Catchments'] = ncatch

        if profile_data:
            durations = parse_profile_durations(profile_data)
            start_date = parse_profile_date(profile_data)
            end_date = start_date + timedelta(days=1)
            for step, duration in durations.items():
                row[f"{step} Duration (s)"] = duration
        else:
            continue

        if ii_forcing:
            execution_duration = durations['FORCINGPROCESSOR']
        else:
            execution_duration = durations['DATASTREAM'] + durations.get('S3_MOVE',5)

        # Extract instance parameters
        instance_params = execution_data.get("instance_parameters", {})
        instance_type = instance_params.get("InstanceType", "N/A")
        run_type = instance_params.get("TagSpecifications", {})[0].get("Tags", [{}])[0].get("Value", "")
        if run_type == "datastream_test": run_type = "datastream_short_range_02"
        run_type_parts = run_type.split('_')
        run_type = '_'.join(run_type_parts[1:-1]) if len(run_type_parts) > 2 else run_type
        row["Run Type"] = run_type    
        row["Instance Type"] = instance_type

        # Fetch dynamic instance details and cost
        vcpu, memory_gib, platform, cost_per_hour = fetch_instance_details(instance_type, pricing_client)
        row["Core Count"] = vcpu if vcpu is not None else "N/A"
        row["Memory (GiB)"] = memory_gib if memory_gib is not None else "N/A"
        row["Platform"] = platform
        row["Instance Cost/hr (InstanceType)"] = cost_per_hour
        estimated_cost_per_execution = cost_per_hour * execution_duration / 3600
        row["Estimated Compute Cost/Execution (BoxUsage)"] = estimated_cost_per_execution
        row["Estimated Compute Cost/Timesteps"] = estimated_cost_per_execution / RUN_TYPE_TIMESTEPS.get(run_type, 1)
        row['Estimated (Catchment * Timesteps) / $'] = (ncatch * RUN_TYPE_TIMESTEPS.get(run_type, 1)) / estimated_cost_per_execution if estimated_cost_per_execution > 0 else 0
        row['Estimated Catchments / Core / Timestep / Second'] = ncatch / (vcpu or 1) / RUN_TYPE_TIMESTEPS.get(run_type, 1) / execution_duration if execution_duration > 0 else 0
        row['Estimated (Catchments * Timesteps) / (Core * Second)'] = (ncatch * RUN_TYPE_TIMESTEPS.get(run_type, 1)) / ((vcpu or 1) * execution_duration) if execution_duration > 0 else 0

        tag_key = instance_params.get("TagSpecifications", {})[0].get("Tags", [{}])[0].get("Key", "")
        tag_value = instance_params.get("TagSpecifications", {})[0].get("Tags", [{}])[0].get("Value", "")
        # observed_cost_per_execution = get_aws_cost(start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'), tag_key, tag_value, "DAILY")
        observed_cost_per_execution = 0
        row["Observed Total Cost/Execution"] = observed_cost_per_execution
        row["Observed Total Cost/Timesteps"] = observed_cost_per_execution / RUN_TYPE_TIMESTEPS.get(run_type, 1)
        row['(Catchment * Timesteps) / Observed Total Cost Per Execution'] = (ncatch * RUN_TYPE_TIMESTEPS.get(run_type, 1)) / observed_cost_per_execution if observed_cost_per_execution > 0 else 0
        row['Observed Catchments / Core / Timestep / Second'] = ncatch / (vcpu or 1) / RUN_TYPE_TIMESTEPS.get(run_type, 1) / execution_duration if execution_duration > 0 else 0
        row['Observed (Catchments * Timesteps) / (Core * Second)'] = (ncatch * RUN_TYPE_TIMESTEPS.get(run_type, 1)) / ((vcpu or 1) * execution_duration) if execution_duration > 0 else 0

        if ii_forcing:
            total_run_size_GB = sum(file_contents.get(".nc", {}).values())
        else:
            total_run_size_GB = file_contents.get("ngen-run.tar.gz", {}).get(vpu_key, 0) + file_contents.get("merkdir.file", {}).get(vpu_key, 0)
        row["Output Data Size in S3 (GB)"] = total_run_size_GB
        row["S3 Cost/Month/GB"] = 0.023
        row["S3 Cost/Month/Execution"] = 0.023 * total_run_size_GB

        # Extract volume parameters
        block_device_mappings = instance_params.get("BlockDeviceMappings", [])
        if block_device_mappings:
            ebs = block_device_mappings[0].get("Ebs", {})
            volume_type = ebs.get("VolumeType", "N/A")
            volume_size = ebs.get("VolumeSize", "N/A")
            row["Run Type"] = run_type
            row["Timesteps"] = RUN_TYPE_TIMESTEPS.get(run_type, 1)
            row["Volume Type"] = volume_type
            row["Volume Size (GB)"] = volume_size

            # Fetch volume cost
            volume_cost_per_hr = 0.08 / 30 / 24
            row["Cost/hr (Volume)"] = volume_cost_per_hr * volume_size  # Total volume cost per hour            
            estimated_volume_cost = volume_cost_per_hr * volume_size * execution_duration / 3600
            row['Estimated Volume Cost / Execution (EBS:VolumeUsage)'] = estimated_volume_cost
        else:
            row["Volume Type"] = "N/A"
            row["Volume Size (GB)"] = "N/A"
            row["Cost/hr (Volume)"] = 0.0
            estimated_volume_cost = 0.0

        # Effective cost: use observed if >0, else estimated compute + volume
        estimated_total = row["Estimated Compute Cost/Execution (BoxUsage)"] + estimated_volume_cost
        row["Effective Total Cost/Execution"] = observed_cost_per_execution if observed_cost_per_execution > 0 else estimated_total

        rows.append(row)

    # Convert rows to a DataFrame
    df = pd.DataFrame(rows)

    return df


def read_files_from_s3(bucket_name, prefix, accepted_file_types, key_pattern):
    """
    Reads files from an S3 bucket matching a prefix and accepted file types.
    Groups file contents by file type and keys extracted using a regex pattern.
    
    Args:
        bucket_name (str): The name of the S3 bucket.
        prefix (str): The prefix (folder path or key prefix) to filter files.
        accepted_file_types (list): List of file types (suffixes) to include.
        key_pattern (str): A regex pattern to extract a key from the file path.
        
    Returns:
        dict: A dictionary where keys are file types and values are dictionaries.
              The inner dictionaries have extracted keys as keys and file contents as values.
    """
    # Initialize S3 client
    s3_client = boto3.client('s3')
    
    # Initialize a dictionary to store file contents grouped by file type
    file_contents = {file_type: {} for file_type in accepted_file_types}
    
    # List all objects under the specified prefix
    paginator = s3_client.get_paginator('list_objects_v2')
    has_content = False
    for page in paginator.paginate(Bucket=bucket_name, Prefix=prefix):
        if 'Contents' in page:
            has_content = True
        for obj in page.get('Contents', []):
            key = obj['Key']
            
            # Check if the file matches any accepted file type
            for file_type in accepted_file_types:
                if key.endswith(file_type):
                    # Extract the desired portion of the prefix using the regex pattern
                    match = re.search(key_pattern, key)
                    if not match:
                        extracted_key = "forcing"
                    else:
                        extracted_key = match.group(0)  # Extracted string (e.g., VPU_02)
                    

                    if file_type in ["merkdir.file", "ngen-run.tar.gz", ".nc"]:
                        response = s3_client.head_object(Bucket=bucket_name, Key=key)
                        file_contents[file_type][extracted_key] = response['ContentLength'] / 1000000000               
                    else:
                        # Download to local cache
                        local_dir = "local_cache/" + prefix.replace('/', '_')
                        os.makedirs(local_dir, exist_ok=True)
                        local_path = local_dir + '/' + extracted_key + '_' + key.split('/')[-1]
                        if not os.path.exists(local_path):
                            s3_client.download_file(bucket_name, key, local_path)
                        with open(local_path, 'r') as f:
                            content = f.read()
                        
                        try:
                            # If file is JSON, parse content. Otherwise, store as raw text.
                            if file_type.endswith('.json'):
                                data = json.loads(content)
                            else:
                                data = content
                            
                            # Store content under the extracted key
                            file_contents[file_type][extracted_key] = data
                            print(f"Successfully read file: {key} (Extracted key: {extracted_key})")
                        except Exception as e:
                            print(f"Failed to read or parse file {key}: {e}")
    
    if not has_content:
        print(f"No contents found for prefix: {prefix}")
    
    return file_contents

def list_subdirectories(bucket_name, prefix):
    """
    List immediate subdirectories under a given S3 prefix.
    
    Args:
        bucket_name (str): Name of the S3 bucket.
        prefix (str): The S3 prefix (acts like a folder path).
    
    Returns:
        List[str]: List of subdirectory names.
    """
    s3_client = boto3.client('s3')
    paginator = s3_client.get_paginator('list_objects_v2')

    # Use the Delimiter to get immediate subdirectories
    result = []
    for page in paginator.paginate(Bucket=bucket_name, Prefix=prefix, Delimiter='/'):
        if 'CommonPrefixes' in page:
            for cp in page['CommonPrefixes']:
                # Extract the prefix (subdirectory name)
                result.append(cp['Prefix'])
    
    return result

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--start_date", required=True, help="Start date in YYYYMMDD format")
    parser.add_argument("--end_date", required=True, help="End date in YYYYMMDD format")
    parser.add_argument("--run_types", nargs='+', required=True, help="Run types, space separated")
    parser.add_argument("--init_cycles", type=str, required=True, help="Init cycles: 'all' or space separated list like 00 06 12 18")
    parser.add_argument("--vpus", type=str, required=True, help="VPUs: 'all' or space separated list like VPU_01 VPU_02")
    parser.add_argument("--sample_date", required=True, help="Sample date in YYYYMMDD format")
    parser.add_argument("--sample_init", required=True, help="Sample init cycle like 06")
    args = parser.parse_args()

    bucket = "ciroh-community-ngen-datastream"
    base_prefix = "v2.2/ngen."
    file_patterns = ["execution.json",
                     "profile.txt",
                     "profile_fp.txt",
                     "filenamelist.txt",
                     "conf_datastream.json",
                     "ngen-run.tar.gz",
                     "merkdir.file",
                     ".nc"]
    key_pattern = r"VPU_\d{2}[A-Za-z]?"

    start = datetime.strptime(args.start_date, '%Y%m%d')
    end = datetime.strptime(args.end_date, '%Y%m%d')
    num_days = (end - start).days + 1

    if args.vpus == "all":
        all_vpus = [k for k in NCATCHMENTS if k.startswith("VPU_")]
    else:
        all_vpus = args.vpus.split()

    total_system_cost = 0.0

    all_df_ngen = []
    all_df_forcing = []
    missing_executions = []

    for run_type in args.run_types:
        if run_type == "analysis_assim_extend":
            sample_d = (datetime.strptime(args.sample_date, '%Y%m%d') - timedelta(days=1)).strftime('%Y%m%d')
            sample_i = "16"
        else:
            sample_d = args.sample_date
            sample_i = args.sample_init

        if args.init_cycles == "all":
            num_inits = RUN_TYPE_INITS_PER_DAY.get(run_type, 1)
        else:
            num_inits = len(args.init_cycles.split())
            if run_type == "analysis_assim_extend":
                num_inits = 1  # Override for analysis_assim_extend

        ens_mems = 1
        if run_type == "medium_range":
            ens_mems = 7

        # Fetch for ngen
        ngen_prefix = base_prefix + sample_d + "/" + run_type + "/" + sample_i + "/"
        files_ngen = read_files_from_s3(bucket, ngen_prefix, file_patterns, key_pattern)
        df_ngen = build_dataframe_from_files(files_ngen, selected_vpus=all_vpus if args.vpus == "all" else None)

        # Check missing VPUs for NGEN
        present_vpus = set(df_ngen['Domain']) if not df_ngen.empty else set()
        for v in all_vpus:
            if v not in present_vpus:
                missing_executions.append(f"run_type: {run_type}, vpu: {v}, date: {sample_d}, init: {sample_i}")

        # Fetch for forcing
        forcing_prefix = base_prefix + sample_d + "/" + "forcing_" + run_type + "/" + sample_i + "/"
        files_forcing = read_files_from_s3(bucket, forcing_prefix, file_patterns, key_pattern)
        df_forcing = build_dataframe_from_files(files_forcing)

        # Check missing for forcing
        if df_forcing.empty:
            missing_executions.append(f"run_type: forcing_{run_type}, date: {sample_d}, init: {sample_i}")

        # Calculate costs per init
        ngen_cost_per_init = df_ngen["Effective Total Cost/Execution"].sum()
        forcing_cost_per_init = df_forcing["Effective Total Cost/Execution"].sum()

        cost_per_init = ngen_cost_per_init * ens_mems + forcing_cost_per_init
        cost_per_day = cost_per_init * num_inits 
        cost_for_period = cost_per_day * num_days

        # Add to total
        total_system_cost += cost_for_period

        # Add column for period cost
        df_ngen['Projected Cost Over Period'] = df_ngen["Effective Total Cost/Execution"] * num_inits * num_days * ens_mems
        df_forcing['Projected Cost Over Period'] = df_forcing["Effective Total Cost/Execution"] * num_inits * num_days

        all_df_ngen.append(df_ngen)
        all_df_forcing.append(df_forcing)

        # Optionally print dfs
        # print(f"NGEN for {run_type}:\n{df_ngen}")
        # print(f"Forcing for {run_type}:\n{df_forcing}")

    print(f"Total projected cost for the system over the period: {total_system_cost}")

    # Combine dataframes
    combined_df_ngen = pd.concat(all_df_ngen, ignore_index=True)
    combined_df_forcing = pd.concat(all_df_forcing, ignore_index=True)

    # Save to CSV
    combined_df_ngen.to_csv('ngen_data.csv', index=False)
    combined_df_forcing.to_csv('forcing_data.csv', index=False)

    # Analysis for most costly aspects
    # For NGEN: group by Run Type and Domain (VPU)
    ngen_cost_by_run_type = combined_df_ngen.groupby('Run Type')['Projected Cost Over Period'].sum().sort_values(ascending=False)
    ngen_cost_by_vpu = combined_df_ngen.groupby('Domain')['Projected Cost Over Period'].sum().sort_values(ascending=False)

    # For Forcing: group by Run Type (since no VPU)
    forcing_cost_by_run_type = combined_df_forcing.groupby('Run Type')['Projected Cost Over Period'].sum().sort_values(ascending=False)

    # Print summaries
    print("\nMost costly run_types for NGEN:")
    print(ngen_cost_by_run_type)
    print("\nMost costly VPUs for NGEN:")
    print(ngen_cost_by_vpu)
    print("\nMost costly run_types for Forcing:")
    print(forcing_cost_by_run_type)

    # Optionally save summaries
    ngen_cost_by_run_type.to_csv('ngen_cost_by_run_type.csv')
    ngen_cost_by_vpu.to_csv('ngen_cost_by_vpu.csv')
    forcing_cost_by_run_type.to_csv('forcing_cost_by_run_type.csv')   

    # Write missing executions to file
    with open('missing_executions.txt', 'w') as f:
        for missing in missing_executions:
            f.write(missing + '\n')