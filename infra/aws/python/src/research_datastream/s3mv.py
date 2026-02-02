#!/usr/bin/env python3
"""
Multithreaded S3 object mover script.
Moves objects from one S3 prefix to another with pattern filtering and parallel execution.

Author: Jordan Laser
jlaser@lynker.com
"""

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Tuple, Optional
import boto3
from botocore.exceptions import ClientError
import threading
from dataclasses import dataclass


@dataclass
class MoveStats:
    """Thread-safe statistics tracker"""
    def __init__(self):
        self.total = 0
        self.moved = 0
        self.skipped = 0
        self.errors = 0
        self.lock = threading.Lock()
        self.last_print = 0
        self.start_time = None
        self.sample_moves = []  # Store sample moves for dry-run display
        self.pattern_sample_moves = []  # Store samples that match the replacement pattern
    
    def start(self):
        """Mark the start time"""
        import time
        self.start_time = time.time()
    
    def add_sample_move(self, source_bucket: str, source_key: str, dest_bucket: str, dest_key: str, has_pattern: bool = False):
        """Add a sample move for dry-run display"""
        with self.lock:
            self.sample_moves.append((source_bucket, source_key, dest_bucket, dest_key))
            if has_pattern:
                self.pattern_sample_moves.append((source_bucket, source_key, dest_bucket, dest_key))
    
    def get_sample_moves(self, first_n: int = 2, last_n: int = 2):
        """Get first N and last N sample moves"""
        with self.lock:
            total = len(self.sample_moves)
            if total <= first_n + last_n:
                return self.sample_moves, []
            return self.sample_moves[:first_n], self.sample_moves[-last_n:]
    
    def get_pattern_samples(self, n: int = 2):
        """Get up to N samples that match the pattern"""
        with self.lock:
            return self.pattern_sample_moves[:n]
    
    def increment_total(self):
        with self.lock:
            self.total += 1
    
    def increment_moved(self):
        with self.lock:
            self.moved += 1
    
    def increment_skipped(self):
        with self.lock:
            self.skipped += 1
    
    def increment_errors(self):
        with self.lock:
            self.errors += 1
    
    def get_stats(self) -> Tuple[int, int, int, int]:
        with self.lock:
            return self.total, self.moved, self.skipped, self.errors
    
    def should_print_progress(self, interval: int = 1000) -> Tuple[bool, int]:
        """
        Check if we should print progress (every N operations).
        Returns tuple of (should_print, current_total)
        """
        with self.lock:
            # Calculate how many intervals have passed since last print
            intervals_passed = (self.total // interval) - (self.last_print // interval)
            
            if intervals_passed >= 1:
                # Update last_print to current interval boundary
                self.last_print = (self.total // interval) * interval
                return True, self.total
            return False, self.total
    
    def get_rate(self) -> float:
        """Get current processing rate (files/second)"""
        import time
        if self.start_time is None:
            return 0.0
        elapsed = time.time() - self.start_time
        if elapsed == 0:
            return 0.0
        with self.lock:
            return self.total / elapsed


def should_process_object(
    key: str,
    contains_pattern: Optional[str],
    ignore_pattern: Optional[str]
) -> Tuple[bool, Optional[str]]:
    """
    Determine if an object should be processed based on patterns.
    
    Returns:
        Tuple of (should_process, skip_reason)
    """
    # Check contains pattern
    if contains_pattern and contains_pattern not in key:
        return False, f"does not contain required pattern '{contains_pattern}'"
    
    # Check ignore pattern
    if ignore_pattern and ignore_pattern in key:
        return False, f"matches ignore pattern '{ignore_pattern}'"
    
    return True, None


def move_object(
    s3_client,
    source_bucket: str,
    dest_bucket: str,
    source_key: str,
    dest_key: str,
    dry_run: bool,
    stats: Optional[MoveStats] = None,
    replace_pattern: Optional[str] = None
) -> Tuple[bool, Optional[str]]:
    """
    Move a single S3 object using copy + delete (same as 'aws s3 mv').
    Supports both same-bucket and cross-bucket moves.
    Includes retry logic for rate limiting and transient errors.
    
    Returns:
        Tuple of (success, error_message)
    """
    if dry_run:
        # Record sample move for display
        if stats:
            has_pattern = replace_pattern and replace_pattern in source_key
            stats.add_sample_move(source_bucket, source_key, dest_bucket, dest_key, has_pattern)
        return True, None
    
    import time
    max_retries = 3
    retry_delay = 1  # Start with 1 second
    
    for attempt in range(max_retries):
        try:
            # Copy object (server-side copy for same region, otherwise downloads/uploads)
            copy_source = {'Bucket': source_bucket, 'Key': source_key}
            s3_client.copy_object(
                CopySource=copy_source,
                Bucket=dest_bucket,
                Key=dest_key
            )
            
            # Delete original
            s3_client.delete_object(Bucket=source_bucket, Key=source_key)
            
            return True, None
        
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            
            # Retry on throttling or transient errors
            if error_code in ['SlowDown', 'ServiceUnavailable', 'RequestTimeout'] and attempt < max_retries - 1:
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
                continue
            
            error_msg = f"Error moving {source_key}: {str(e)}"
            return False, error_msg
    
    return False, f"Failed after {max_retries} retries"




def process_object(
    args: Tuple,
    stats: MoveStats,
    progress_interval: int
) -> None:
    """
    Process a single object (check patterns and move if needed).
    This function is called by worker threads.
    """
    (s3_client, source_bucket, dest_bucket, object_key, prefix_old, prefix_new,
     contains_pattern, ignore_pattern, replace_pattern, with_pattern, dry_run) = args
    
    # Check if object should be processed
    should_process, skip_reason = should_process_object(
        object_key, contains_pattern, ignore_pattern
    )
    
    if not should_process:
        stats.increment_total()
        stats.increment_skipped()
        # Print progress after incrementing
        should_print, current_total = stats.should_print_progress(progress_interval)
        if should_print:
            total, moved, skipped, errors = stats.get_stats()
            rate = stats.get_rate()
            print(f"Progress: {total:,} processed | {moved:,} moved | {skipped:,} skipped | {errors:,} errors | Rate: {rate:.1f} files/sec")
        return
    
    # Calculate new key
    relative_path = object_key[len(prefix_old):].lstrip('/')
    
    # Apply pattern replacement if specified
    if replace_pattern is not None:
        # Allow empty string for with_pattern (to delete the pattern)
        replacement = with_pattern if with_pattern is not None else ""
        relative_path = relative_path.replace(replace_pattern, replacement)
    
    new_key = f"{prefix_new}/{relative_path}"
    
    # Move the object
    success, error = move_object(
        s3_client, source_bucket, dest_bucket, object_key, new_key, dry_run, stats, replace_pattern
    )
    
    if success:
        stats.increment_total()
        stats.increment_moved()
    else:
        stats.increment_total()
        stats.increment_errors()
        # Always print errors
        print(f"[ERROR] {error}", file=sys.stderr)
    
    # Print progress after incrementing
    should_print, current_total = stats.should_print_progress(progress_interval)
    if should_print:
        total, moved, skipped, errors = stats.get_stats()
        rate = stats.get_rate()
        print(f"Progress: {total:,} processed | {moved:,} moved | {skipped:,} skipped | {errors:,} errors | Rate: {rate:.1f} files/sec")


def list_objects(s3_client, bucket: str, prefix: str) -> List[str]:
    """
    List all objects with the given prefix.
    """
    objects = []
    paginator = s3_client.get_paginator('list_objects_v2')
    
    print(f"Listing objects at s3://{bucket}/{prefix}/...")
    print("(This may take a while for large prefixes...)")
    
    # Ensure prefix ends with / for proper filtering
    search_prefix = f"{prefix}/" if not prefix.endswith('/') else prefix
    
    try:
        page_count = 0
        for page in paginator.paginate(Bucket=bucket, Prefix=search_prefix):
            if 'Contents' in page:
                page_count += 1
                for obj in page['Contents']:
                    # Double-check that the object actually starts with our prefix/
                    # This prevents matching "v2.2abc/" when we want "v2.2/"
                    if obj['Key'].startswith(search_prefix):
                        objects.append(obj['Key'])
                
                # Print progress every 10 pages (10,000 objects)
                if page_count % 10 == 0:
                    print(f"  Listed {len(objects):,} objects so far...")
        
        print(f"\nFound {len(objects):,} total objects")
        return objects
    
    except ClientError as e:
        print(f"Error listing objects: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description='Move S3 objects from one prefix to another with multithreading',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Move within same bucket
  %(prog)s --source_bucket my-bucket --prefix_old v2.2 --prefix_new outputs/v2.2 --dry-run
  
  # Move to different bucket with pattern replacement
  %(prog)s --source_bucket source-bucket --dest_bucket dest-bucket \\
    --prefix_old data/v2.2 --prefix_new data/v2.2 \\
    --replace_pattern SHORT_RANGE --with_pattern short_range \\
    --threads 20
  
  # Delete a pattern from file paths (remove unwanted directory)
  %(prog)s --source_bucket my-bucket --prefix_old v2.2 --prefix_new v2.2 \\
    --delete_pattern metadata.csv/ \\
    --threads 30
  
  # Move only files containing 'forcing', replace pattern in path
  %(prog)s --source_bucket my-bucket --prefix_old v2.2 --prefix_new v2.2_new \\
    --contains_pattern forcing --replace_pattern UPPER --with_pattern lower \\
    --progress_interval 5000
        """
    )
    
    parser.add_argument('--source_bucket', required=True,
                        help='Source S3 bucket name')
    parser.add_argument('--dest_bucket', required=False, default=None,
                        help='Destination S3 bucket name (defaults to source_bucket if not specified)')
    parser.add_argument('--prefix_old', required=True,
                        help='Current prefix path in source bucket')
    parser.add_argument('--prefix_new', required=True,
                        help='New prefix path in destination bucket')
    parser.add_argument('--ignore_pattern', default=None,
                        help='Pattern to ignore (files containing this will be skipped)')
    parser.add_argument('--contains_pattern', default=None,
                        help='Pattern to match (only files containing this will be moved)')
    parser.add_argument('--replace_pattern', default=None,
                        help='Pattern to find and replace in the file path (case-sensitive)')
    parser.add_argument('--with_pattern', default=None,
                        help='Replacement pattern (used with --replace_pattern). Use empty string "" to delete.')
    parser.add_argument('--delete_pattern', default=None,
                        help='Pattern to delete from the file path (shorthand for --replace_pattern X --with_pattern "")')
    parser.add_argument('--threads', type=int, default=10,
                        help='Number of parallel threads (default: 10)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would be done without actually moving files')
    parser.add_argument('--progress_interval', type=int, default=1000,
                        help='Print progress every N files (default: 1000)')
    parser.add_argument('--skip', type=int, default=0,
                        help='Skip the first N files (useful for resuming, default: 0)')
    parser.add_argument('--profile', default=None,
                        help='AWS profile name to use (optional)')
    parser.add_argument('--region', default=None,
                        help='AWS region (optional)')
    
    args = parser.parse_args()
    
    # Validate pattern replacement/deletion args
    if args.delete_pattern and (args.replace_pattern or args.with_pattern):
        print("Error: --delete_pattern cannot be used with --replace_pattern or --with_pattern")
        sys.exit(1)
    
    if args.with_pattern and not args.replace_pattern:
        print("Error: --with_pattern requires --replace_pattern to be specified")
        sys.exit(1)
    
    # Convert delete_pattern to replace_pattern with empty replacement
    if args.delete_pattern:
        args.replace_pattern = args.delete_pattern
        args.with_pattern = ""
    
    # Set destination bucket to source bucket if not specified
    dest_bucket = args.dest_bucket if args.dest_bucket else args.source_bucket
    
    # Remove trailing slashes
    prefix_old = args.prefix_old.rstrip('/')
    prefix_new = args.prefix_new.rstrip('/')
    
    # Print configuration
    print("=" * 60)
    print("S3 Object Move Script (Multithreaded)")
    print("=" * 60)
    print(f"Source Bucket:    {args.source_bucket}")
    print(f"Dest Bucket:      {dest_bucket}")
    print(f"Old Prefix:       {prefix_old}")
    print(f"New Prefix:       {prefix_new}")
    print(f"Ignore Pattern:   {args.ignore_pattern or '(none)'}")
    print(f"Contains Pattern: {args.contains_pattern or '(none)'}")
    if args.replace_pattern:
        if args.with_pattern:
            print(f"Replace Pattern:  '{args.replace_pattern}' -> '{args.with_pattern}'")
        else:
            print(f"Delete Pattern:   '{args.replace_pattern}' (remove from path)")
    print(f"Threads:          {args.threads}")
    print(f"Progress Every:   {args.progress_interval:,} files")
    print(f"Dry Run:          {args.dry_run}")
    print("=" * 60)
    print()
    
    # Create boto3 session and client
    session_kwargs = {}
    if args.profile:
        session_kwargs['profile_name'] = args.profile
    if args.region:
        session_kwargs['region_name'] = args.region
    
    session = boto3.Session(**session_kwargs)
    s3_client = session.client('s3')
    
    # List all objects from source bucket
    objects = list_objects(s3_client, args.source_bucket, prefix_old)
    
    if not objects:
        print("No objects found to process")
        return
    
    # Apply skip if specified (for resume capability)
    if args.skip > 0:
        if args.skip >= len(objects):
            print(f"Skip value ({args.skip}) is >= total objects ({len(objects)}). Nothing to do.")
            return
        print(f"Skipping first {args.skip:,} objects (resume mode)")
        objects = objects[args.skip:]
    
    print()
    print(f"Processing {len(objects):,} objects with {args.threads} threads...")
    print()
    
    # Initialize statistics
    stats = MoveStats()
    stats.start()
    
    # Prepare arguments for each worker
    worker_args = [
        (s3_client, args.source_bucket, dest_bucket, obj, prefix_old, prefix_new,
         args.contains_pattern, args.ignore_pattern, args.replace_pattern, 
         args.with_pattern, args.dry_run)
        for obj in objects
    ]
    
    # Process objects in parallel
    with ThreadPoolExecutor(max_workers=args.threads) as executor:
        futures = [
            executor.submit(process_object, arg, stats, args.progress_interval)
            for arg in worker_args
        ]
        
        # Wait for all tasks to complete
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                print(f"[ERROR] Unexpected error: {e}", file=sys.stderr)
                stats.increment_errors()
    
    # Print summary
    total, moved, skipped, errors = stats.get_stats()
    rate = stats.get_rate()
    
    print()
    print("=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"Total objects found:    {total:,}")
    print(f"Objects moved:          {moved:,}")
    print(f"Objects skipped:        {skipped:,}")
    print(f"Errors:                 {errors:,}")
    print(f"Average rate:           {rate:.1f} files/sec")
    print("=" * 60)
    
    if args.dry_run:
        print()
        print("This was a dry run. No objects were actually moved.")
        print("Remove --dry-run to execute the move operation.")
        
        # Display sample moves
        first_samples, last_samples = stats.get_sample_moves(first_n=2, last_n=2)
        
        if first_samples or last_samples:
            print()
            print("=" * 60)
            print("Sample File Moves (Dry-Run Preview)")
            print("=" * 60)
            
            # If pattern replacement is active, show samples with the pattern
            if args.replace_pattern:
                pattern_affected = len(stats.pattern_sample_moves)
                total_samples = len(stats.sample_moves)
                print(f"\nPattern '{args.replace_pattern}' found in {pattern_affected:,} of {total_samples:,} files")
                
                if pattern_affected == 0:
                    print(f"⚠️  WARNING: No files contain the pattern '{args.replace_pattern}'")
                    print(f"   The pattern will have no effect. Check your pattern spelling.")
                else:
                    # Show samples that actually have the pattern
                    pattern_samples = stats.get_pattern_samples(n=2)
                    if pattern_samples:
                        print(f"\nExample files WITH pattern '{args.replace_pattern}':")
                        for i, (src_bucket, src_key, dst_bucket, dst_key) in enumerate(pattern_samples, 1):
                            print(f"\n  {i}. Source:")
                            print(f"     s3://{src_bucket}/{src_key}")
                            print(f"     Destination:")
                            print(f"     s3://{dst_bucket}/{dst_key}")
                            if src_key != dst_key:
                                print(f"     ✓ Pattern removed from path")
            
            if first_samples:
                print("\n" + "-" * 60)
                print("First 2 files overall:")
                for i, (src_bucket, src_key, dst_bucket, dst_key) in enumerate(first_samples, 1):
                    print(f"\n  {i}. Source:")
                    print(f"     s3://{src_bucket}/{src_key}")
                    print(f"     Destination:")
                    print(f"     s3://{dst_bucket}/{dst_key}")
            
            if last_samples and len(first_samples) + len(last_samples) > len(first_samples):
                print(f"\n  ... ({moved - len(first_samples) - len(last_samples):,} files in between) ...")
                print(f"\nLast 2 files overall:")
                for i, (src_bucket, src_key, dst_bucket, dst_key) in enumerate(last_samples, moved - len(last_samples) + 1):
                    print(f"\n  {i}. Source:")
                    print(f"     s3://{src_bucket}/{src_key}")
                    print(f"     Destination:")
                    print(f"     s3://{dst_bucket}/{dst_key}")
            
            print("\n" + "=" * 60)


if __name__ == '__main__':
    main()
