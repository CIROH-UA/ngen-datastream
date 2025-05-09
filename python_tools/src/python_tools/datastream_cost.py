import argparse
import boto3
import json
import pandas as pd
import re
from datetime import datetime, timedelta
from botocore.exceptions import BotoCoreError, ClientError

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

def build_dataframe_from_files(file_contents):
    """
    Builds a pandas DataFrame from parsed S3 file contents.

    Args:
        file_contents (dict): Dictionary of file contents grouped by file type and keys (e.g., VPU_02).

    Returns:
        pd.DataFrame: DataFrame with execution details and profiling step durations.
    """
    rows = []

    # Initialize AWS Pricing client
    pricing_client = boto3.client('pricing', region_name='us-east-1')

    # Iterate over execution.json files
    for vpu_key, execution_data in file_contents.get("execution.json", {}).items():
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

        ncatch = NCATCHMENTS[vpu_key]
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

        rows.append(row)

        # Extract instance parameters
        instance_params = execution_data.get("instance_parameters", {})
        instance_type = instance_params.get("InstanceType", "N/A")
        run_type = instance_params.get("TagSpecifications", {})[0].get("Tags")[0].get("Value")
        if run_type == "datastream_test": run_type = "datastream_short_range_02"
        run_type = run_type.split('_')[1:-1]
        run_type = '_'.join(run_type) 
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
        row["Estimated Compute Cost/Timesteps"] = estimated_cost_per_execution / RUN_TYPE_TIMESTEPS[run_type]
        row['Estimated (Catchment * Timesteps) / $'] = (ncatch * RUN_TYPE_TIMESTEPS[run_type]) / estimated_cost_per_execution
        row['Estimated Catchments / Core / Timestep / Second'] = ncatch / vcpu / RUN_TYPE_TIMESTEPS[run_type] / execution_duration
        row['Estimated (Catchments * Timesteps) / (Core * Second)'] = (ncatch * RUN_TYPE_TIMESTEPS[run_type]) / (vcpu * execution_duration)

        observed_cost_per_execution = get_aws_cost(start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'), instance_params.get("TagSpecifications", {})[0].get("Tags")[0].get("Key"), instance_params.get("TagSpecifications", {})[0].get("Tags")[0].get("Value"), "DAILY")
        row["Observed Total Cost/Execution"] = observed_cost_per_execution
        row["Observed Total Cost/Timesteps"] = observed_cost_per_execution / RUN_TYPE_TIMESTEPS[run_type]
        row['(Catchment * Timesteps) / Observed Total Cost Per Execution'] = (ncatch * RUN_TYPE_TIMESTEPS[run_type]) / observed_cost_per_execution
        row['Observed Catchments / Core / Timestep / Second'] = ncatch / vcpu / RUN_TYPE_TIMESTEPS[run_type] / execution_duration
        row['Observed (Catchments * Timesteps) / (Core * Second)'] = (ncatch * RUN_TYPE_TIMESTEPS[run_type]) / (vcpu * execution_duration)

        if ii_forcing:
            total_run_size_GB = sum(file_contents.get(".nc", 0).values())
        else:
            total_run_size_GB = file_contents.get("ngen-run.tar.gz", 0).get(vpu_key) + file_contents.get("merkdir.file", 0).get(vpu_key)
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
            row["Timesteps"] = RUN_TYPE_TIMESTEPS[run_type]
            row["Volume Type"] = volume_type
            row["Volume Size (GB)"] = volume_size

            # Fetch volume cost
            volume_cost_per_hr = 0.08 / 30 / 24
            row["Cost/hr (Volume)"] = volume_cost_per_hr * volume_size  # Total volume cost per hour            
            row['Estimated Volume Cost / Execution (EBS:VolumeUsage)'] = volume_cost_per_hr * volume_size * execution_duration / 3600
        else:
            row["Volume Type"] = "N/A"
            row["Volume Size (GB)"] = "N/A"
            row["Cost/hr (Volume)"] = 0.0

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
    response = s3_client.list_objects_v2(Bucket=bucket_name, Prefix=prefix)
    
    # Iterate over files in the bucket
    for obj in response.get('Contents', []):
        key = obj['Key']
        
        # Check if the file matches any accepted file type
        for file_type in accepted_file_types:
            if key.endswith(file_type):
                # Extract the desired portion of the prefix using the regex pattern
                match = re.search(key_pattern, key)
                if not match:
                    extracted_key = "forcing"
                    # print(f"No match found for pattern '{key_pattern}' in key '{key}'. Skipping.")
                    # continue
                else:
                    extracted_key = match.group(0)  # Extracted string (e.g., VPU_02)
                

                if file_type == "merkdir.file" or file_type == "ngen-run.tar.gz" or file_type == ".nc":
                    response = s3_client.head_object(Bucket=bucket_name, Key=key)
                    file_contents[file_type][extracted_key] = response['ContentLength'] / 1000000000               
                else:
                    # Read the file content
                    response = s3_client.get_object(Bucket=bucket_name, Key=key)
                    content = response['Body'].read().decode('utf-8')
                    
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
    parser.add_argument("--ngen_run_type_prefix", help="s3 URI to datastream date and run_type",default=None)
    parser.add_argument("--start_date", help="start_date",default=None)
    parser.add_argument("--end_date", help="end_date",default=None)
    parser.add_argument("--out_file", help="plot output directory",default=None)
    args = parser.parse_args()

    bucket = "ciroh-community-ngen-datastream"
    s3_prefix = args.ngen_run_type_prefix
    file_patterns = ["execution.json",
                     "profile.txt",
                     "profile_fp.txt",
                     "filenamelist.txt",
                     "conf_datastream.json",
                     "ngen-run.tar.gz",
                     "merkdir.file",
                     ".nc"]
    
    start = datetime.strptime(args.start_date,'%Y-%m-%d')
    end = datetime.strptime(args.end_date,'%Y-%m-%d')
    dates = pd.date_range(start,end-timedelta(days=1),freq='d')

    dfs_forcing_all = []
    dfs_ngen_all = []
    for jdate in dates:
        dfs_forcing = []
        dfs_ngen = []
        for jprefix in list_subdirectories(bucket,s3_prefix+jdate.strftime('%Y%m%d')+'/'):        
            files = read_files_from_s3(bucket,
                                        jprefix,
                                        file_patterns,
                                        r"VPU_\d{2}[A-Za-z]?"
                                        )    
            df = build_dataframe_from_files(files)
            if "forcing" in jprefix:
                dfs_forcing.append(df)
            else:
                dfs_ngen.append(df)

        forcing_columns = list(dfs_forcing[0].columns)
        reorder = [19,0,1,8,9,10,11,12,13,14,15,16,17,18,20,21,22,23,24,2,3,4,5,6,7]
        columns_reordered = [forcing_columns[i] for i in reorder]
        df_forcing = pd.concat(dfs_forcing,ignore_index=True)
        df_forcing.reindex(columns=columns_reordered)
        dfs_forcing_all.append(df_forcing)

        ngen_columns = list(dfs_ngen[1].columns)
        reorder = [0,1,2,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,3,4,5,6,7,8,9,10]
        columns_reordered = [ngen_columns[i] for i in reorder]    
        df_ngen = pd.concat(dfs_ngen,ignore_index=True)
        dfs_ngen_all.append(df_ngen)

    df_forcing = pd.concat(dfs_forcing_all)
    df_forcing_avg = df_forcing.groupby(df_forcing.select_dtypes(exclude='number').columns.tolist()).mean().reset_index()

    df_ngen = pd.concat(dfs_ngen_all)
    df_ngen_avg = df_ngen.groupby(df_ngen.select_dtypes(exclude='number').columns.tolist()).mean().reset_index()

    conus_ngen_df = df_ngen_avg.groupby("Run Type")["Number of Catchments"].sum().reset_index()
    conus_ngen_df = pd.merge(conus_ngen_df,df_ngen_avg.groupby("Run Type")["Observed Total Cost/Execution"].sum().reset_index(), on="Run Type", how="inner")
    conus_ngen_df['Executions/Day'] = [1, 4, 24]
    conus_ngen_df['Projected Total Cost/Day'] = conus_ngen_df['Observed Total Cost/Execution'] * conus_ngen_df['Executions/Day']
    conus_ngen_df['Projected Total Cost/Year'] = conus_ngen_df['Projected Total Cost/Day'] * 365    
    conus_ngen_df['CONUS Projected Total Cost/Day'] = conus_ngen_df['Projected Total Cost/Day'] * ( NCATCHMENTS['forcing'] / conus_ngen_df['Number of Catchments'] )
    conus_ngen_df['CONUS Projected Total Cost/Year'] = conus_ngen_df['Projected Total Cost/Year'] * ( NCATCHMENTS['forcing'] / conus_ngen_df['Number of Catchments'] ) 

    conus_forcing_df = df_forcing_avg.groupby("Run Type")["Number of Catchments"].sum().reset_index()
    conus_forcing_df = pd.merge(conus_forcing_df,df_ngen_avg.groupby("Run Type")["Observed Total Cost/Execution"].sum().reset_index(), on="Run Type", how="inner")
    conus_forcing_df['Executions/Day'] = [1, 4, 24]
    conus_forcing_df['Projected Total Cost/Day'] = conus_forcing_df['Observed Total Cost/Execution'] * conus_forcing_df['Executions/Day']
    conus_forcing_df['Projected Total Cost/Year'] = conus_forcing_df['Projected Total Cost/Day'] * 365    
    conus_forcing_df['CONUS Projected Total Cost/Day'] = conus_forcing_df['Projected Total Cost/Day'] * ( NCATCHMENTS['forcing'] / conus_forcing_df['Number of Catchments'] )
    conus_forcing_df['CONUS Projected Total Cost/Year'] = conus_forcing_df['Projected Total Cost/Year'] * ( NCATCHMENTS['forcing'] / conus_forcing_df['Number of Catchments'] )   

    with pd.ExcelWriter(args.out_file + f"/{args.start_date}" + f"_{args.end_date}.xlsx") as writer:
        conus_forcing_df.to_excel(writer, sheet_name='conus_forcing_yearly', index=False)
        conus_ngen_df.to_excel(writer, sheet_name='conus_ngen_yearly', index=False)
        df_forcing_avg.to_excel(writer, sheet_name='conus_forcing_daily', index=False)
        df_ngen_avg.to_excel(writer, sheet_name='VPU_ngen_daily', index=False)
