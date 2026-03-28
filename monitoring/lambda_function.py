import boto3
import re
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
import json

# Configuration
S3_BUCKET = "ciroh-community-ngen-datastream"
NUM_DAYS = 5  # Number of days to check (including today)
OUTPUT_KEY = "status/dashboard.html"

scheduler = boto3.client('scheduler')
s3 = boto3.client('s3')


def get_all_schedules():
    """Get all schedule names"""
    schedules = []
    paginator = scheduler.get_paginator('list_schedules')
    for page in paginator.paginate():
        for sched in page['Schedules']:
            schedules.append(sched['Name'])
    return schedules


def get_schedule_details(name):
    """Get schedule details including S3 prefix"""
    try:
        response = scheduler.get_schedule(Name=name)
        if 'Input' not in response.get('Target', {}):
            return None

        input_str = response['Target']['Input']
        match = re.search(r'--S3_PREFIX\s+([^\s\'\"]+)', input_str)
        if not match:
            return None

        prefix = match.group(1)
        parts = prefix.split('/')
        model = parts[1] if len(parts) > 1 else 'unknown'

        forecast_type = None
        for part in parts:
            if part in ['short_range', 'medium_range', 'analysis_assim_extend']:
                forecast_type = part
                break

        ngiab_tag_match = re.search(r'NGIAB_TAG=([^\s&\'\"]+)', input_str)
        ngiab_tag = ngiab_tag_match.group(1) if ngiab_tag_match else None

        created_date = response.get('CreationDate')
        created_str = created_date.strftime('%Y%m%d') if created_date else None

        return {
            'name': name,
            'prefix': prefix,
            'model': model,
            'forecast_type': forecast_type,
            'ngiab_tag': ngiab_tag,
            'created_date': created_str
        }
    except Exception as e:
        return None


def list_tar_files_for_model(args):
    """List ngen-run.tar.gz files for a specific model and date"""
    model, date = args
    files = set()
    paginator = s3.get_paginator('list_objects_v2')
    prefix = f"outputs/{model}/v2.2_hydrofabric/ngen.{date}/"

    for page in paginator.paginate(Bucket=S3_BUCKET, Prefix=prefix):
        for obj in page.get('Contents', []):
            key = obj['Key']
            if key.endswith('ngen-run.tar.gz'):
                path = key.rsplit('/ngen-run.tar.gz', 1)[0]
                files.add(path)

    return files


def list_existing_tar_files(date, models):
    """List all ngen-run.tar.gz files for a given date using parallel S3 list_objects"""
    existing_files = set()

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(list_tar_files_for_model, (model, date)): model for model in models}
        for future in as_completed(futures):
            files = future.result()
            existing_files.update(files)

    return existing_files


def generate_html_multi_day(all_results, dates, updated_at, execution_time):
    """Generate HTML dashboard for multiple days"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="refresh" content="3600">
    <title>NRDS Output Status Dashboard</title>
    <style>
        * {{ box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 0; padding: 20px; background: #f5f5f5;
        }}
        .container {{ max-width: 1400px; margin: 0 auto; }}
        h1 {{ color: #333; margin-bottom: 5px; }}
        .updated {{ color: #666; font-size: 14px; margin-bottom: 20px; }}
        .date-section {{
            background: white; border-radius: 8px; padding: 20px;
            margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .date-header {{
            display: flex; justify-content: space-between; align-items: center;
            margin-bottom: 15px; padding-bottom: 10px; border-bottom: 2px solid #eee;
        }}
        .date-title {{ font-size: 22px; font-weight: bold; color: #333; }}
        .date-summary {{ font-size: 16px; color: #666; }}
        .progress-bar {{
            width: 100%; height: 25px; background: #e0e0e0; border-radius: 12px;
            overflow: hidden; margin: 10px 0;
        }}
        .progress-fill {{ height: 100%; transition: width 0.3s; background: #4caf50; }}
        .forecast-section {{
            background: #fafafa; border-radius: 6px; padding: 15px;
            margin-bottom: 10px; border: 1px solid #eee;
        }}
        .forecast-header {{
            display: flex; justify-content: space-between; align-items: center;
            cursor: pointer; padding: 8px; background: #f0f0f0; border-radius: 4px;
        }}
        .forecast-header:hover {{ background: #e8e8e8; }}
        .forecast-name {{ font-weight: 600; font-size: 14px; }}
        .forecast-stats {{ display: flex; gap: 10px; align-items: center; }}
        .count {{ font-size: 13px; min-width: 90px; text-align: right; }}
        .mini-progress {{
            width: 120px; height: 16px; background: #e0e0e0; border-radius: 8px;
            overflow: hidden;
        }}
        .missing-section {{
            margin-top: 10px; padding: 12px; background: #fff3e0;
            border: 1px solid #ffb74d; border-radius: 4px; display: none;
        }}
        .missing-section.open {{ display: block; }}
        .missing-section.all-complete {{
            background: #e8f5e9; border-color: #81c784;
        }}
        .missing-title {{ font-weight: 600; color: #e65100; margin-bottom: 8px; font-size: 13px; }}
        .missing-section.all-complete .missing-title {{ color: #2e7d32; }}
        .missing-item {{
            display: inline-block; background: #fff3cd; color: #856404;
            padding: 3px 6px; border-radius: 3px; margin: 2px; font-size: 11px;
            font-family: monospace;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>NRDS Status Dashboard</h1>
        <p class="updated">Last updated: {updated_at} UTC</p>

"""

    for date in dates:
        results = all_results[date]

        by_type = {}
        for r in results:
            ftype = r.get('forecast_type', 'other')
            model = r.get('model', 'unknown')
            key = f"{model}_{ftype}"
            if key not in by_type:
                by_type[key] = {'exists': [], 'missing': [], 'model': model, 'forecast_type': ftype, 'ngiab_tag': r.get('ngiab_tag')}
            if r['exists']:
                by_type[key]['exists'].append(r)
            else:
                by_type[key]['missing'].append(r)

        total_exists = sum(len(d['exists']) for d in by_type.values())
        total_missing = sum(len(d['missing']) for d in by_type.values())
        total = total_exists + total_missing
        overall_pct = (total_exists / total * 100) if total > 0 else 0

        formatted_date = f"{date[:4]}-{date[4:6]}-{date[6:]}"

        html += f"""
        <div class="date-section">
            <div class="date-header">
                <span class="date-title">{formatted_date}</span>
                <span class="date-summary">{total_exists} / {total} ({overall_pct:.1f}%)</span>
            </div>
            <div class="progress-bar">
                <div class="progress-fill" style="width: {overall_pct}%"></div>
            </div>
"""

        for key in sorted(by_type.keys()):
            data = by_type[key]
            exists_count = len(data['exists'])
            missing_count = len(data['missing'])
            total_count = exists_count + missing_count
            pct = (exists_count / total_count * 100) if total_count > 0 else 0

            ngiab_tag = data.get('ngiab_tag')
            display_name = f"{data['model'].upper()} - {data['forecast_type'].replace('_', ' ').title()}"
            if ngiab_tag:
                display_name += f" (NGIAB - {ngiab_tag})"
            section_id = f"{date}_{key}"

            html += f"""
            <div class="forecast-section">
                <div class="forecast-header" onclick="toggleSection('{section_id}')">
                    <span class="forecast-name">{display_name}</span>
                    <div class="forecast-stats">
                        <div class="mini-progress">
                            <div class="progress-fill" style="width: {pct}%"></div>
                        </div>
                        <span class="count">{exists_count} / {total_count} ({pct:.1f}%)</span>
                    </div>
                </div>
                <div id="{section_id}" class="missing-section {'all-complete' if missing_count == 0 else ''}">
"""

            if missing_count == 0:
                html += '                    <div class="missing-title">All outputs complete!</div>\n'
            else:
                html += f'                    <div class="missing-title">In Progress ({missing_count}):</div>\n'
                for m in sorted(data['missing'], key=lambda x: x['name']):
                    html += f'                    <span class="missing-item">{m["name"]}</span>\n'

            html += """                </div>
            </div>
"""

        html += """        </div>
"""

    html += """    </div>
    <script>
        function toggleSection(id) {
            const section = document.getElementById(id);
            section.classList.toggle('open');
        }
    </script>
</body>
</html>
"""
    return html


def lambda_handler(event, context):
    """Main Lambda handler"""
    start_time = datetime.now(timezone.utc)
    print("Starting dashboard generation...")

    today = datetime.now(timezone.utc)
    dates = [(today - timedelta(days=i)).strftime('%Y%m%d') for i in range(NUM_DAYS)]
    print(f"Checking dates: {dates}")

    # Fetch all schedules
    print("Fetching all schedules...")
    schedule_names = [name for name in get_all_schedules() if 'test' not in name.lower()]
    print(f"Found {len(schedule_names)} schedules")

    # Get schedule details
    print("Getting schedule details...")
    schedule_details = []
    with ThreadPoolExecutor(max_workers=50) as executor:
        futures = {executor.submit(get_schedule_details, name): name for name in schedule_names}
        for future in as_completed(futures):
            result = future.result()
            if result:
                schedule_details.append(result)

    print(f"Got details for {len(schedule_details)} schedules with S3 prefixes")

    # Get unique models
    models = list(set(sched['model'] for sched in schedule_details))
    print(f"Models to check: {models}")

    # Check each date
    all_results = {}

    for date in dates:
        print(f"Listing S3 objects for {date}...")
        existing_files = list_existing_tar_files(date, models)
        print(f"  Found {len(existing_files)} ngen-run.tar.gz files")

        results = []
        for sched in schedule_details:
            # Skip schedules created after this date
            if sched.get('created_date') and date < sched['created_date']:
                continue
            updated_prefix = sched['prefix'].replace('DAILY', date)
            exists = updated_prefix in existing_files

            results.append({
                'name': sched['name'],
                'path': f"s3://{S3_BUCKET}/{updated_prefix}/ngen-run.tar.gz",
                'exists': exists,
                'forecast_type': sched['forecast_type'],
                'model': sched['model'],
                'ngiab_tag': sched.get('ngiab_tag'),
                'date': date
            })

        results.sort(key=lambda x: x['name'])
        all_results[date] = results

        exists_count = sum(1 for r in results if r['exists'])
        missing_count = sum(1 for r in results if not r['exists'])
        print(f"  {date}: {exists_count} exist, {missing_count} missing")

    execution_time = (datetime.now(timezone.utc) - start_time).total_seconds()
    print(f"Data fetched in {execution_time:.1f}s")

    # Generate HTML
    updated_at = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')
    html = generate_html_multi_day(all_results, dates, updated_at, execution_time)

    # Upload to S3
    s3.put_object(
        Bucket=S3_BUCKET,
        Key=OUTPUT_KEY,
        Body=html,
        ContentType='text/html',
        CacheControl='max-age=300'
    )

    print(f"Dashboard uploaded to s3://{S3_BUCKET}/{OUTPUT_KEY}")

    # Build summary
    summary = {}
    for date in dates:
        results = all_results[date]
        summary[date] = {
            'ngen_exists': sum(1 for r in results if r['exists']),
            'ngen_missing': sum(1 for r in results if not r['exists']),
            'ngen_total': len(results)
        }

    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': 'Dashboard generated',
            'dates': dates,
            'summary': summary,
            'execution_time_seconds': execution_time,
            'output': f"s3://{S3_BUCKET}/{OUTPUT_KEY}"
        })
    }


if __name__ == "__main__":
    result = lambda_handler({}, None)
    print(result)
