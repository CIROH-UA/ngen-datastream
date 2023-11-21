'''
Borrowed from Nels Fraizer's subset.py in data_access_examples
'''
from pathlib import Path
import geopandas as gpd
import pandas as pd

def make_x_walk(hydrofabric):
    """
    Borrowed from https://github.com/NOAA-OWP/ngen/pull/464
    Args:
        hydrofabric (_type_): _description_
    """
    attributes = gpd.read_file(hydrofabric, layer="flowpath_attributes").set_index("id")
    x_walk = pd.Series(attributes[~attributes["rl_gages"].isna()]["rl_gages"])

    data = {}
    for wb, gage in x_walk.items():
        data[wb] = {"Gage_no": [gage]}
    import json

    with open("crosswalk.json", "w") as fp:
        json.dump(data, fp, indent=2)

def make_geojson(hydrofabric: Path):
    """Create the various required geojson/json files from the geopkg
    Borrowed from https://github.com/NOAA-OWP/ngen/pull/464

    Args:
        hydrofabric (Path): path to hydrofabric geopkg
    """
    try:
        catchments = gpd.read_file(hydrofabric, layer="divides")
        nexuses = gpd.read_file(hydrofabric, layer="nexus")
        flowpaths = gpd.read_file(hydrofabric, layer="flowpaths")
        edge_list = pd.DataFrame(
            gpd.read_file(hydrofabric, layer="flowpath_edge_list").drop(
                columns="geometry"
            )
        )
        make_x_walk(hydrofabric)
        catchments.to_file("catchments.geojson")
        nexuses.to_file("nexus.geojson")
        flowpaths.to_file("flowpaths.geojson")
        edge_list.to_json("flowpath_edge_list.json", orient="records", indent=2)
    except Exception as e:
        print(f"Unable to use hydrofabric file {hydrofabric}")
        print(str(e))
        raise e

if __name__ == "__main__":
    import argparse

    # get the command line parser
    parser = argparse.ArgumentParser(description="Subset provided hydrofabric")
    parser.add_argument(
        "hydrofabric", type=Path, help="Path or link to hydrofabric geopkg to"
    )

    args = parser.parse_args()
    make_geojson(args.hydrofabric)