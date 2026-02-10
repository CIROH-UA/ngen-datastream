import boto3
import re
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
import json

# Configuration
S3_BUCKET = "ciroh-community-ngen-datastream"
NUM_DAYS = 5  # Number of days to check (including today)
OUTPUT_KEY = "status/dashboard.html"

# Expected VPUs for forcing processor
EXPECTED_VPUS = ['01', '02', '03W', '03N', '03S', '04', '05', '06', '07', '08', '09', '10L', '10U', '11', '12', '13', '14', '15', '16', '17', '18']

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

        return {
            'name': name,
            'prefix': prefix,
            'model': model,
            'forecast_type': forecast_type
        }
    except Exception as e:
        return None


def get_fp_schedule_details(name):
    """Get forcing processor schedule details"""
    try:
        response = scheduler.get_schedule(Name=name)
        if 'Input' not in response.get('Target', {}):
            return None

        input_str = response['Target']['Input']

        # Extract S3 prefix for forcing processor
        # Pattern: s3://bucket/forcings/v2.2_hydrofabric/ngen.DAILY/forcing_short_range/00
        match = re.search(r's3://[^/]+/([^\s\'\"]+)', input_str)
        if not match:
            return None

        prefix = match.group(1)

        # Must be a forcings path
        if not prefix.startswith('forcings/'):
            return None

        # Extract forecast type and cycle from schedule name
        # Pattern: short_range_fcst00_vpufp_schedule_cfe_nom
        forecast_match = re.search(r'(short_range|medium_range|analysis_assim_extend)_fcst(\d+)', name)
        if not forecast_match:
            return None

        forecast_type = f"forcing_{forecast_match.group(1)}"
        cycle = int(forecast_match.group(2))

        return {
            'name': name,
            'prefix': prefix,
            'forecast_type': forecast_type,
            'cycle': cycle
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


def list_forcing_files_for_schedule(args):
    """List forcing files for a specific schedule and date"""
    date, forecast_type, cycle = args
    files = {}
    paginator = s3.get_paginator('list_objects_v2')
    prefix = f"forcings/v2.2_hydrofabric/ngen.{date}/{forecast_type}/{cycle:02d}/"

    for page in paginator.paginate(Bucket=S3_BUCKET, Prefix=prefix):
        for obj in page.get('Contents', []):
            key = obj['Key']
            if key.endswith('.nc') and 'VPU_' in key:
                match = re.search(r'VPU_(\w+)\.nc$', key)
                if match:
                    vpu = match.group(1)
                    files[vpu] = True

    return (forecast_type, cycle, files)


def list_existing_forcing_files(date, fp_schedules):
    """List all forcing files for a given date based on schedules"""
    results = {}

    # Build tasks from schedules
    tasks = []
    seen = set()
    for sched in fp_schedules:
        key = (sched['forecast_type'], sched['cycle'])
        if key not in seen:
            seen.add(key)
            tasks.append((date, sched['forecast_type'], sched['cycle']))

    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(list_forcing_files_for_schedule, task): task for task in tasks}
        for future in as_completed(futures):
            forecast_type, cycle, files = future.result()
            if forecast_type not in results:
                results[forecast_type] = {}
            results[forecast_type][cycle] = files

    return results


def generate_html_multi_day(all_results, all_forcing_results, fp_schedules, dates, updated_at, execution_time):
    """Generate HTML dashboard for multiple days with tabs"""

    # Group FP schedules by forecast type
    fp_by_type = {}
    for sched in fp_schedules:
        ftype = sched['forecast_type']
        if ftype not in fp_by_type:
            fp_by_type[ftype] = set()
        fp_by_type[ftype].add(sched['cycle'])

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
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

        .tab-container {{
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
        }}
        .tab {{
            padding: 12px 24px;
            background: #e0e0e0;
            border: none;
            border-radius: 8px 8px 0 0;
            cursor: pointer;
            font-size: 16px;
            font-weight: 600;
            transition: background 0.2s;
        }}
        .tab:hover {{
            background: #d0d0d0;
        }}
        .tab.active {{
            background: white;
            box-shadow: 0 -2px 4px rgba(0,0,0,0.1);
        }}
        .tab-content {{
            display: none;
        }}
        .tab-content.active {{
            display: block;
        }}

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
        .progress-fill {{ height: 100%; transition: width 0.3s; }}
        .progress-fill.complete {{ background: #4caf50; }}
        .progress-fill.partial {{ background: #ff9800; }}
        .progress-fill.low {{ background: #f44336; }}
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
            display: inline-block; background: #ffcdd2; color: #c62828;
            padding: 3px 6px; border-radius: 3px; margin: 2px; font-size: 11px;
            font-family: monospace;
        }}
        .legend {{
            display: flex; gap: 20px; margin-bottom: 20px; font-size: 14px;
        }}
        .legend-item {{ display: flex; align-items: center; gap: 5px; }}
        .legend-box {{ width: 16px; height: 16px; border-radius: 3px; }}
        .legend-box.ok {{ background: #c8e6c9; }}
        .legend-box.missing {{ background: #ffcdd2; }}

        .cycle-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(80px, 1fr));
            gap: 8px;
            margin-top: 10px;
        }}
        .cycle-box {{
            padding: 8px;
            border-radius: 4px;
            text-align: center;
            font-size: 12px;
            font-weight: 600;
        }}
        .cycle-box.complete {{ background: #c8e6c9; color: #2e7d32; }}
        .cycle-box.partial {{ background: #fff3e0; color: #e65100; }}
        .cycle-box.missing {{ background: #ffcdd2; color: #c62828; }}
        .vpu-list {{
            margin-top: 5px;
            font-size: 10px;
            font-weight: normal;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>NRDS Status Dashboard</h1>
        <p class="updated">Last updated: {updated_at} UTC (auto-refreshes every hour) | Data fetched in {execution_time:.1f}s</p>

        <div class="tab-container">
            <button class="tab active" onclick="showTab('ngen')">NextGen Outputs</button>
            <button class="tab" onclick="showTab('forcing')">Forcing Processor</button>
        </div>

        <div class="legend">
            <div class="legend-item"><div class="legend-box ok"></div> Complete</div>
            <div class="legend-item"><div class="legend-box missing"></div> Missing</div>
        </div>

        <div id="ngen-tab" class="tab-content active">
"""

    # NextGen outputs tab
    for date in dates:
        results = all_results[date]

        by_type = {}
        for r in results:
            ftype = r.get('forecast_type', 'other')
            model = r.get('model', 'unknown')
            key = f"{model}_{ftype}"
            if key not in by_type:
                by_type[key] = {'exists': [], 'missing': [], 'model': model, 'forecast_type': ftype}
            if r['exists']:
                by_type[key]['exists'].append(r)
            else:
                by_type[key]['missing'].append(r)

        total_exists = sum(len(d['exists']) for d in by_type.values())
        total_missing = sum(len(d['missing']) for d in by_type.values())
        total = total_exists + total_missing
        overall_pct = (total_exists / total * 100) if total > 0 else 0

        formatted_date = f"{date[:4]}-{date[4:6]}-{date[6:]}"
        pct_class = 'complete' if overall_pct >= 95 else 'partial' if overall_pct >= 50 else 'low'

        html += f"""
        <div class="date-section">
            <div class="date-header">
                <span class="date-title">{formatted_date}</span>
                <span class="date-summary">{total_exists} / {total} ({overall_pct:.1f}%)</span>
            </div>
            <div class="progress-bar">
                <div class="progress-fill {pct_class}" style="width: {overall_pct}%"></div>
            </div>
"""

        for key in sorted(by_type.keys()):
            data = by_type[key]
            exists_count = len(data['exists'])
            missing_count = len(data['missing'])
            total_count = exists_count + missing_count
            pct = (exists_count / total_count * 100) if total_count > 0 else 0

            display_name = f"{data['model'].upper()} - {data['forecast_type'].replace('_', ' ').title()}"
            section_id = f"{date}_{key}"
            pct_class = 'complete' if pct >= 95 else 'partial' if pct >= 50 else 'low'

            html += f"""
            <div class="forecast-section">
                <div class="forecast-header" onclick="toggleSection('{section_id}')">
                    <span class="forecast-name">{display_name}</span>
                    <div class="forecast-stats">
                        <div class="mini-progress">
                            <div class="progress-fill {pct_class}" style="width: {pct}%"></div>
                        </div>
                        <span class="count">{exists_count} / {total_count} ({pct:.1f}%)</span>
                    </div>
                </div>
                <div id="{section_id}" class="missing-section {'all-complete' if missing_count == 0 else ''}">
"""

            if missing_count == 0:
                html += '                    <div class="missing-title">✓ All outputs complete!</div>\n'
            else:
                html += f'                    <div class="missing-title">Missing ({missing_count}):</div>\n'
                for m in sorted(data['missing'], key=lambda x: x['name']):
                    html += f'                    <span class="missing-item">{m["name"]}</span>\n'

            html += """                </div>
            </div>
"""

        html += """        </div>
"""

    html += """        </div>

        <div id="forcing-tab" class="tab-content">
"""

    # Forcing Processor tab - now based on schedules
    for date in dates:
        forcing_results = all_forcing_results.get(date, {})
        formatted_date = f"{date[:4]}-{date[4:6]}-{date[6:]}"

        # Calculate totals based on scheduled cycles only
        total_expected = 0
        total_exists = 0
        for forecast_type, cycles in fp_by_type.items():
            for cycle in cycles:
                total_expected += len(EXPECTED_VPUS)
                cycle_data = forcing_results.get(forecast_type, {}).get(cycle, {})
                total_exists += len(cycle_data)

        overall_pct = (total_exists / total_expected * 100) if total_expected > 0 else 0
        pct_class = 'complete' if overall_pct >= 95 else 'partial' if overall_pct >= 50 else 'low'

        html += f"""
        <div class="date-section">
            <div class="date-header">
                <span class="date-title">{formatted_date}</span>
                <span class="date-summary">{total_exists} / {total_expected} VPU files ({overall_pct:.1f}%)</span>
            </div>
            <div class="progress-bar">
                <div class="progress-fill {pct_class}" style="width: {overall_pct}%"></div>
            </div>
"""

        for forecast_type in sorted(fp_by_type.keys()):
            cycles = sorted(fp_by_type[forecast_type])
            display_name = forecast_type.replace('forcing_', '').replace('_', ' ').title()

            type_expected = len(cycles) * len(EXPECTED_VPUS)
            type_exists = 0
            for cycle in cycles:
                cycle_data = forcing_results.get(forecast_type, {}).get(cycle, {})
                type_exists += len(cycle_data)

            type_pct = (type_exists / type_expected * 100) if type_expected > 0 else 0
            type_pct_class = 'complete' if type_pct >= 95 else 'partial' if type_pct >= 50 else 'low'
            section_id = f"fp_{date}_{forecast_type}"

            html += f"""
            <div class="forecast-section">
                <div class="forecast-header" onclick="toggleSection('{section_id}')">
                    <span class="forecast-name">{display_name}</span>
                    <div class="forecast-stats">
                        <div class="mini-progress">
                            <div class="progress-fill {type_pct_class}" style="width: {type_pct}%"></div>
                        </div>
                        <span class="count">{type_exists} / {type_expected} ({type_pct:.1f}%)</span>
                    </div>
                </div>
                <div id="{section_id}" class="missing-section">
                    <div class="missing-title">Cycles:</div>
                    <div class="cycle-grid">
"""

            for cycle in cycles:
                cycle_data = forcing_results.get(forecast_type, {}).get(cycle, {})
                existing_vpus = set(cycle_data.keys())
                missing_vpus = set(EXPECTED_VPUS) - existing_vpus

                cycle_pct = (len(existing_vpus) / len(EXPECTED_VPUS) * 100) if EXPECTED_VPUS else 0
                cycle_class = 'complete' if cycle_pct >= 100 else 'partial' if cycle_pct > 0 else 'missing'

                html += f"""                        <div class="cycle-box {cycle_class}">
                            {cycle:02d}Z
                            <div class="vpu-list">{len(existing_vpus)}/{len(EXPECTED_VPUS)}</div>
                        </div>
"""

            html += """                    </div>
                </div>
            </div>
"""

        html += """        </div>
"""

    html += """        </div>
    </div>
    <script>
        function toggleSection(id) {
            const section = document.getElementById(id);
            section.classList.toggle('open');
        }

        function showTab(tabName) {
            document.querySelectorAll('.tab-content').forEach(tab => {
                tab.classList.remove('active');
            });
            document.querySelectorAll('.tab').forEach(btn => {
                btn.classList.remove('active');
            });

            document.getElementById(tabName + '-tab').classList.add('active');
            event.target.classList.add('active');
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
    schedule_names = get_all_schedules()
    print(f"Found {len(schedule_names)} schedules")

    # Get NextGen schedule details
    print("Getting NextGen schedule details...")
    schedule_details = []
    fp_schedule_details = []

    with ThreadPoolExecutor(max_workers=50) as executor:
        # NextGen schedules
        ngen_futures = {executor.submit(get_schedule_details, name): name for name in schedule_names}
        # FP schedules (filter by name pattern)
        fp_names = [n for n in schedule_names if 'vpufp' in n.lower() or 'forcing' in n.lower()]
        fp_futures = {executor.submit(get_fp_schedule_details, name): name for name in fp_names}

        for future in as_completed(ngen_futures):
            result = future.result()
            if result:
                schedule_details.append(result)

        for future in as_completed(fp_futures):
            result = future.result()
            if result:
                fp_schedule_details.append(result)

    print(f"Got details for {len(schedule_details)} NextGen schedules")
    print(f"Got details for {len(fp_schedule_details)} FP schedules")

    # Get unique models
    models = list(set(sched['model'] for sched in schedule_details))
    print(f"Models to check: {models}")

    # Check each date
    all_results = {}
    all_forcing_results = {}

    for date in dates:
        # NextGen outputs
        print(f"Listing S3 objects for {date}...")
        existing_files = list_existing_tar_files(date, models)
        print(f"  Found {len(existing_files)} ngen-run.tar.gz files")

        results = []
        for sched in schedule_details:
            updated_prefix = sched['prefix'].replace('DAILY', date)
            exists = updated_prefix in existing_files

            results.append({
                'name': sched['name'],
                'path': f"s3://{S3_BUCKET}/{updated_prefix}/ngen-run.tar.gz",
                'exists': exists,
                'forecast_type': sched['forecast_type'],
                'model': sched['model'],
                'date': date
            })

        results.sort(key=lambda x: x['name'])
        all_results[date] = results

        exists_count = sum(1 for r in results if r['exists'])
        missing_count = sum(1 for r in results if not r['exists'])
        print(f"  {date}: {exists_count} exist, {missing_count} missing")

        # Forcing files - based on schedules
        print(f"Listing forcing files for {date}...")
        forcing_results = list_existing_forcing_files(date, fp_schedule_details)
        all_forcing_results[date] = forcing_results

        forcing_count = sum(
            len(files)
            for cycles in forcing_results.values()
            for files in cycles.values()
        )
        print(f"  {date}: {forcing_count} forcing VPU files found")

    execution_time = (datetime.now(timezone.utc) - start_time).total_seconds()
    print(f"Data fetched in {execution_time:.1f}s")

    # Generate HTML
    updated_at = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')
    html = generate_html_multi_day(all_results, all_forcing_results, fp_schedule_details, dates, updated_at, execution_time)

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
    fp_by_type = {}
    for sched in fp_schedule_details:
        ftype = sched['forecast_type']
        if ftype not in fp_by_type:
            fp_by_type[ftype] = set()
        fp_by_type[ftype].add(sched['cycle'])

    summary = {}
    for date in dates:
        results = all_results[date]
        forcing_results = all_forcing_results[date]

        fp_exists = sum(
            len(files)
            for cycles in forcing_results.values()
            for files in cycles.values()
        )
        fp_expected = sum(len(cycles) * len(EXPECTED_VPUS) for cycles in fp_by_type.values())

        summary[date] = {
            'ngen_exists': sum(1 for r in results if r['exists']),
            'ngen_missing': sum(1 for r in results if not r['exists']),
            'ngen_total': len(results),
            'fp_exists': fp_exists,
            'fp_expected': fp_expected
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
