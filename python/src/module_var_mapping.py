from __future__ import annotations
from typing import Literal
from typing_extensions import TypeAlias

ModelName: TypeAlias = str
InputOrOutput = Literal["input", "output"]
VarName: TypeAlias = str
VarAlias: TypeAlias = str

models_with_alias: dict[
    ModelName, dict[InputOrOutput, set[VarName | tuple[VarName, VarAlias]]]
] = {
    "pet": {
        "input": {
            "land_surface_radiation~incoming~longwave__energy_flux",
            "land_surface_radiation~incoming~shortwave__energy_flux",
            "land_surface_air__pressure",
            "atmosphere_air_water~vapor__relative_saturation",
            "land_surface_air__temperature",
            "land_surface_wind__x_component_of_velocity",
            "land_surface_wind__y_component_of_velocity",
        },
        "output": {"water_potential_evaporation_flux"},
    },
    "noah_owp_modular": {
        "input": {
            ("SFCPRS", "land_surface_air__pressure"),
            ("SFCTMP", "land_surface_air__temperature"),
            ("SOLDN", "land_surface_radiation~incoming~shortwave__energy_flux"),
            ("LWDN", "land_surface_radiation~incoming~longwave__energy_flux"),
            ("UU", "land_surface_wind__x_component_of_velocity"),
            ("VV", "land_surface_wind__y_component_of_velocity"),
            ("Q2", "atmosphere_air_water~vapor__mixing_ratio"),
            ("PRCPNONC", "atmosphere_water__precipitation_leq-volume_flux"),
        },
        "output": {
            ("QINSUR", "soil_surface_water__potential_infiltration_volume_flux"),
            ("ETRAN", "land_vegetation_canopy_water__transpiration_volume_flux"),
            ("QSEVA", "land_surface_water__evaporation_volume_flux"),
            ("EVAPOTRANS", "land_surface_water__evapotranspiration_volume_flux"),
            ("TG", "land_surface__temperature"),
            ("SNEQV", "snowpack__liquid-equivalent_depth"),
            "TGS",
            "ACSNOM",
            "SNOWT_AVG",
            "ISNOW",
            "QRAIN",
            "FSNO",
            "SNOWH",
            "SNLIQ",
            "QSNOW",
            "ECAN",
            "GH",
            "TRAD",
            "FSA",
            "CMC",
            "LH",
            "FIRA",
            "FSH",
        },
    },
    "cfe": {
        "input": {
            "atmosphere_water__liquid_equivalent_precipitation_rate",
            "water_potential_evaporation_flux",
            "ice_fraction_schaake",
            "ice_fraction_xinanjiang",
            "soil_moisture_profile",
        },
        "output": {
            "RAIN_RATE",
            "DIRECT_RUNOFF",
            "GIUH_RUNOFF",
            "NASH_LATERAL_RUNOFF",
            "DEEP_GW_TO_CHANNEL_FLUX",
            "SOIL_TO_GW_FLUX",
            "Q_OUT",
            "POTENTIAL_ET",
            "ACTUAL_ET",
            "GW_STORAGE",
            "SOIL_STORAGE",
            "SOIL_STORAGE_CHANGE",
            "SURF_RUNOFF_SCHEME",
        },
    },
    "soil_moisture_profile": {
        "input": {
            "soil_storage",
            "soil_storage_change",
            "num_wetting_fronts",
            "soil_moisture_wetting_fronts",
            "soil_depth_wetting_fronts",
            "Qb_topmodel",
            "Qv_topmodel",
            "global_deficit",
        },
        "output": {
            "soil_moisture_profile",
            "soil_water_table",
            "soil_moisture_fraction",
        },
    },
    "soil_freeze_thaw": {
        "input": {
            "ground_temperature",
            "soil_moisture_profile",
        },
        "output": {
            "ice_fraction_schaake",
            "ice_fraction_xinanjiang",
            "num_cells",
            "soil_temperature_profile",
            "soil_ice_fraction",
            "ground_heat_flux",
        },
    },
    "lgar": {
        "input": {
            "precipitation_rate",
            "potential_evapotranspiration_rate",
            "soil_temperature_profile",
        },
        "output": {
            "soil_moisture_wetting_fronts",
            "soil_depth_layers",
            "soil_depth_wetting_fronts",
            "soil_num_wetting_fronts",
            "precipitation",
            "potential_evapotranspiration",
            "actual_evapotranspiration",
            "surface_runoff",
            "giuh_runoff",
            "soil_storage",
            "total_discharge",
            "infiltration",
            "percolation",
            "groundwater_to_stream_recharge",
            "mass_balance",
        },
    },
    "lstm": {
        "input": {
            "land_surface_radiation~incoming~longwave__energy_flux",
            "land_surface_air__pressure",
            "atmosphere_air_water~vapor__relative_saturation",
            "atmosphere_water__liquid_equivalent_precipitation_rate",
            "land_surface_radiation~incoming~shortwave__energy_flux",
            "land_surface_air__temperature",
            "land_surface_wind__x_component_of_velocity",
            "land_surface_wind__y_component_of_velocity",
        },
        "output": {
            "land_surface_water__runoff_depth",
            "land_surface_water__runoff_volume_flux",
        },
    },
    "snow17": {
        "input": {
            "tair",
            "precip",
        },
        "output": {
            "precip_scf",
            "sneqv",
            "snowh",
            "raim",
        },
    },
    "sac_sma": {
        "input": {
            "tair",
            "precip",
            "pet",
        },
        "output": {
            "qs",
            "qg",
            "tci",
            "eta",
            "roimp",
            "baseflow",
            "sdro",
            "ssur",
            "sif",
            "bfs",
            "bfp",
            "bfncc",
        },
    },
}
 
forcing = {
    "aorc": {
        # "precip_rate": "atmosphere_water__liquid_equivalent_precipitation_rate",
        "APCP_surface": "atmosphere_water__rainfall_volume_flux",
        # "DLWRF_surface": "land_surface_radiation~incoming~longwave__energy_flux",
        # "DSWRF_surface": "land_surface_radiation~incoming~shortwave__energy_flux",
        "PRES_surface": "land_surface_air__pressure",
        # "SPFH_2maboveground": "atmosphere_air_water~vapor__relative_saturation",
        # "TMP_2maboveground": "land_surface_air__temperature",
        # "UGRD_10maboveground": "land_surface_wind__x_component_of_velocity",
        # "VGRD_10maboveground": "land_surface_wind__y_component_of_velocity",
        "RAINRATE": "atmosphere_water__liquid_equivalent_precipitation_rate",
        "T2D": "land_surface_air__temperature",
        "Q2D": "atmosphere_air_water~vapor__relative_saturation",
        "U2D": "land_surface_wind__x_component_of_velocity",
        "V2D": "land_surface_wind__y_component_of_velocity",
        # "PSFC": "land_surface_air__pressure",
        "SWDOWN": "land_surface_radiation~incoming~shortwave__energy_flux",
        "LWDOWN": "land_surface_radiation~incoming~longwave__energy_flux",
    },
}
