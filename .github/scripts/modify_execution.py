#!/usr/bin/env python3
"""
Modify execution JSON files for testing.
This script modifies commands in execution template files, preserving all escape sequences.
"""

import json
import sys
import os
import re

def modify_execution(input_file, output_file, run_type, vpu, date, github_run_id):
    """Modify execution JSON commands for testing."""

    # Read the JSON file
    with open(input_file, 'r') as f:
        data = json.load(f)

    # Modify each command
    modified_commands = []
    for cmd in data.get('commands', []):
        # Replace date patterns
        cmd = cmd.replace('v2.2/ngen.DAILY/', f'v2.2/ngen.{date}/')
        cmd = cmd.replace('ngen.DAILY/forcing_', f'ngen.{date}/forcing_')

        # Add end date to -s DAILY - use 1 hour for faster testing
        cmd = cmd.replace('-s DAILY ', f'-s DAILY -e {date}0100 ')

        # Use 7 processors for m8g.2xlarge instances (8 vCPUs, leave 1 for system)
        # Match both $NPROCS and numeric values (gen_vpu_execs.py may have already replaced it)
        cmd = re.sub(r'-n (?:\$NPROCS|-?\d+)', '-n 7', cmd)

        # Replace S3_PREFIX - handle various path patterns
        # Pattern 1: --S3_PREFIX outputs/cfe_nom/v2.2_hydrofabric/ngen.DAILY/...
        # Pattern 2: --S3_PREFIX v2.2/ngen.DAILY/...
        # Pattern 3: --s3_prefix (lowercase for FP templates)
        if '--S3_PREFIX ' in cmd:
            # Match any S3_PREFIX value up to the next quote or whitespace
            cmd = re.sub(
                r'--S3_PREFIX [^\s"\\]+',
                f'--S3_PREFIX tests/{run_type}/VPU_{vpu}',
                cmd
            )
        elif '--s3_prefix ' in cmd:
            # FP template pattern (lowercase)
            cmd = re.sub(
                r'--s3_prefix [^\s"\\]+',
                f'--s3_prefix tests/{run_type}/VPU_{vpu}',
                cmd
            )

        modified_commands.append(cmd)

    data['commands'] = modified_commands

    # Modify tags - add GitHubRunId for safe cleanup
    data['instance_parameters']['TagSpecifications'] = [{
        "ResourceType": "instance",
        "Tags": [
            {"Key": "Project", "Value": f"test_{run_type}_vpu_{vpu}"},
            {"Key": "AMI_Version", "Value": "test-version"},
            {"Key": "GitHubRunId", "Value": github_run_id}
        ]
    }]

    # Write the modified JSON
    with open(output_file, 'w') as f:
        json.dump(data, f, indent=2)

if __name__ == '__main__':
    if len(sys.argv) != 7:
        print(f"Usage: {sys.argv[0]} <input_file> <output_file> <run_type> <vpu> <date> <github_run_id>", file=sys.stderr)
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2]
    run_type = sys.argv[3]
    vpu = sys.argv[4]
    date = sys.argv[5]
    github_run_id = sys.argv[6]

    modify_execution(input_file, output_file, run_type, vpu, date, github_run_id)
