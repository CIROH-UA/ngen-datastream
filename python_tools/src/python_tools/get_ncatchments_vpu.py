import boto3
import json

# Initialize S3 client
s3_client = boto3.client('s3')

def count_key_value_pairs(json_data):
    try:
        data = json.loads(json_data)
        if isinstance(data, dict):
            return len(data)  # Return the number of key-value pairs
        else:
            return 0
    except json.JSONDecodeError:
        return 0

def process_s3_files(bucket_name, prefix):
    # List objects in the bucket with the given prefix
    response = s3_client.list_objects_v2(Bucket=bucket_name, Prefix=prefix)

    if 'Contents' not in response:
        print(f"No files found with prefix '{prefix}' in bucket '{bucket_name}'.")
        return

    for obj in response['Contents']:
        file_key = obj['Key']
        
        # Download file content
        file_obj = s3_client.get_object(Bucket=bucket_name, Key=file_key)
        file_content = file_obj['Body'].read().decode('utf-8')

        # Count the key-value pairs in the JSON file
        num_pairs = count_key_value_pairs(file_content)
        print(f"File: {file_key}, Key-Value Pairs: {num_pairs}")

# Example usage
bucket_name = 'datastream-resources'
prefix = 'weights'
process_s3_files(bucket_name, prefix)
