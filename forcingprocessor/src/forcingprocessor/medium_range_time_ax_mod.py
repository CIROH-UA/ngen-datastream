# Author: Jordan Laser, Lynker
# 
# This script reads in a NRDS forcing file and shifts the time coordinate for medium range ensemble members
# https://github.com/CIROH-UA/ngen-datastream/issues/202
import xarray as xr
from pathlib import Path
import numpy as np
from datetime import datetime, timezone
import re
from forcingprocessor.utils import make_forcing_netcdf


def get_shifted_time_axis(ds:xr.Dataset, ens_member:int, time_shift_hours:int=6) -> np.ndarray:
    """
    Shift the time axis of the dataset based on the ensemble member.

    # https://onlinelibrary.wiley.com/doi/epdf/10.1111/1752-1688.13184
    
    Parameters:
    ds (xarray.Dataset): Input dataset with Time coordinate.
    ens_member (int): Ensemble member number (2-7).
    time_shift_hours (int): Number of hours to shift the time coordinate.
    
    Returns:
    np.ndarray: Shifted time axis.
    """
    t_shift = 3600 * (ens_member - 1) * time_shift_hours
    t0 = ds_in.Time.values[0, 0]
    shift_array = t_shift * np.ones((204,), dtype='float64')
    tax_array = ds.Time.values[0, :-36] + shift_array
    tf = tax_array[0]
    print(f"First time in time array is {datetime.fromtimestamp(t0, tz=timezone.utc)} and was shifed forward {t_shift/3600:.0f} hours to {datetime.fromtimestamp(tf, tz=timezone.utc)}")
    return tax_array

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Shift time coordinate for medium range ensemble members"
    )
    parser.add_argument(
        "--input_file_ens0",
        type=str,
        required=True,
        help="Input NRDS forcing file. Must be from first ensemble member (ens0)",
    )
    parser.add_argument(
        "--output_dir",
        type=str,
        required=False,
        default=".",
        help="Output NRDS forcing file with shifted time coordinate",
    )
    parser.add_argument(
        "--ensemble_member",
        type=str,
        required=True,
        help="Ensember member (2-7)",
    )

    time_shift_hours = 6

    args = parser.parse_args()
    assert Path(args.output_dir).is_dir(), "Output directory does not exist"

    # Shift time axis
    ds_in = xr.open_dataset(args.input_file_ens0)
    ens_member = int(args.ensemble_member)
    if ens_member > 1 and ens_member < 8:
        tax_array = get_shifted_time_axis(ds_in, ens_member, time_shift_hours)
    else: 
        raise ValueError("Ensemble member must be between 2 and 7")
    
    pattern = r'^ngen\.t\d{2}z\.medium_range\.forcing\.f001_f240\.VPU_\d+\.nc$'
    input_file = Path(args.input_file_ens0).name
    if re.match(pattern, input_file):
        out_filename = input_file.replace('f001_f240', 'f001_f204')
    else:
        out_filename = "forcings_ens_" + str(ens_member) + ".nc"
    out_path = Path(args.output_dir) / out_filename 

    nvar = len(ds_in.variables) - 2  # Exclude the time and catchment ids variable
    ncat= ds_in["UGRD_10maboveground"].shape[0]
    data_array = np.ones((ncat,204,nvar),dtype='float64')
    vars = list(ds_in.keys())
    vars.remove('Time')
    vars.remove('ids')
    for j, jvar in enumerate(vars):
        data_array[:,:,j] = ds_in[jvar].values[:, :-36]

    make_forcing_netcdf(out_path,
                        catchments=ds_in.ids.values,
                        t_ax=tax_array,
                        input_array=data_array)