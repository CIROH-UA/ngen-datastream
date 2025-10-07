        # Build matrix from created files - improved version
        matrix_items=()
        for file in rerun_execution_files/*.json; do
          if [ ! -f "$file" ]; then
            continue
          fi
          
          basename_file=$(basename "$file")
          
          # Parse filename: {type}_{cycle}_{ensemble_or_vpu}_{vpu}_{date}.json
          if [[ "$basename_file" =~ ^medium_range_([0-9]{2})_([0-9])_([^_]+)_([0-9]{8})\.json$ ]]; then
            cycle="${BASH_REMATCH[1]}"
            ensemble="${BASH_REMATCH[2]}"
            vpu="${BASH_REMATCH[3]}"
            date="${BASH_REMATCH[4]}"
            type="medium_range"
          elif [[ "$basename_file" =~ ^short_range_([0-9]{2})_([^_]+)_([0-9]{8})\.json$ ]]; then
            cycle="${BASH_REMATCH[1]}"
            vpu="${BASH_REMATCH[2]}"
            date="${BASH_REMATCH[3]}"
            type="short_range"
            ensemble="0"
          elif [[ "$basename_file" =~ ^analysis_assim_extend_([0-9]{2})_([^_]+)_([0-9]{8})\.json$ ]]; then
            cycle="${BASH_REMATCH[1]}"
            vpu="${BASH_REMATCH[2]}"
            date="${BASH_REMATCH[3]}"
            type="analysis_assim_extend"
            ensemble="0"
          else
            echo "WARNING: Could not parse filename: $basename_file"
            continue
          fi
          
          matrix_items+=("{\"type\":\"$type\",\"cycle\":\"$cycle\",\"ensemble\":\"$ensemble\",\"vpu\":\"$vpu\",\"date\":\"$date\",\"file\":\"$basename_file\"}")
        done
        
        # Create matrix JSON
        if [ ${#matrix_items[@]} -eq 0 ]; then
          echo "ERROR: No execution files were created!"
          echo "::error::Failed to create rerun matrix - no execution files generated"
          exit 1
        fi
        
        # Join array elements with commas and wrap in matrix structure
        IFS=','
        matrix_json="{\"include\":[${matrix_items[*]}]}"
        unset IFS
