from forcingprocessor.medium_range_time_ax_mod import cut_forcing_data_for_ensemble
import xarray as xr
import numpy as np

# Member 2, cutting data from time axis index 6 to 210
# Member 3, cutting data from time axis index 12 to 216
# Member 4, cutting data from time axis index 18 to 222
# Member 5, cutting data from time axis index 24 to 228
# Member 6, cutting data from time axis index 30 to 234
# Member 7, cutting data from time axis index 36 to 240
member_shifts = {
    2: (6, 210),
    3: (12, 216),
    4: (18, 222),
    5: (24, 228),
    6: (30, 234),
    7: (36, 240)
}

def test_cut_ens_data():
    ncat = 1000
    ntime = 240
    vars = ['UGRD_10maboveground', 'VGRD_10maboveground', 'TMP_2maboveground']
    data = {var: (('ids', 'time'), np.random.rand(ncat, ntime)) for var in vars}
    data['ids'] = (('catchment-ids',), np.array([ncatember for ncatember in range(ncat)]))
    data['Time'] = ('catchment-ids','time'), np.tile(np.array([np.datetime64('2023-01-01T00:00') + np.timedelta64(i, 'h') for i in range(ntime)]),(ncat,1))
    ds = xr.Dataset(data)
    for ens_member in range(2, 8):
        ds_cut = cut_forcing_data_for_ensemble(ds, ens_member)
        assert ds_cut.UGRD_10maboveground.shape[1] == 204, "Output data does not have 204 time steps"
        assert ds_cut.Time.shape[1] == 204, "Output time axis does not have 204 time steps"
        assert ds_cut.Time.values[0,0] == ds.Time.values[0,member_shifts[ens_member][0]], "Output time axis start does not match expected value"        

if __name__ == "__main__":
    test_cut_ens_data()