#!/usr/bin/env python
"""subset.py
Module for subsetting hyfeatures based ngen hydrofabric geopackages.

@author Nels Frazier
@email nfrazier@lynker.com
@version 0.1
"""

from pathlib import Path
import geopandas as gpd
import pandas as pd
import fiona
from queue import Queue

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import List


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


def get_upstream_ids(divides, nexus, catchment_id):
    """Get the ids of the elements upstream from catchment_id

    Derived from https://github.com/NOAA-OWP/DMOD/blob/3a6da86cac3061116b9a1e2ccdd4a3d01222f0d3/python/lib/modeldata/dmod/modeldata/subset/subset_handler.py#L212

    Args:
        divides (_type_): _description_
        nexus (_type_): _description_
        catchment_id (_type_): _description_

    Returns:
        _type_: _description_
    """
    # print(divides)
    nex_index = nexus[["id", "toid"]].set_index(
        "id"
    )  # pd.Series(nexus['toid'], index = nexus['id'])#
    nex_index["toid"] = nex_index["toid"].str.replace("wb", "cat")
    cat_index = divides[["id", "toid"]].set_index("id")
    link_limit = None
    catchment_ids = [catchment_id]
    graph_nodes = Queue()

    # print(cat_index)
    # debug = cat_index.reset_index()['id'].str.replace('cat-', '').astype(int).sort_values()
    # print(debug)
    # print(debug[ (debug > 113050) & (debug < 113070) ])
    # import os
    # os._exit(1)
    for cid in catchment_ids:
        graph_nodes.put((catchment_id, 0, True))
        try:
            graph_nodes.put((cat_index.loc[cid].item(), 0, False))
        except:
            raise Exception(f'catchment id {cid} is not found in geopackage!')


    cat_ids = set()
    nex_ids = set()

    while graph_nodes.qsize() > 0:
        item, link_dist, is_catchment = graph_nodes.get()
        if item is None:
            continue
        if is_catchment and item not in cat_ids:
            cat_ids.add(item)
            if link_limit is None or link_dist < link_limit:
                new_dist = link_dist + 1
                # find the nexus linked to the upstream of this catchment
                inflow = nex_index[nex_index["toid"] == item].index.unique()
                if len(inflow) == 1:
                    graph_nodes.put((inflow[0], new_dist, False))
                elif len(inflow) > 1:
                    print("WARNING: Catchment network is not dendridict")
                # If it is 0, we found a headwater, which is fine...
        elif not is_catchment and item not in nex_ids:
            nex_ids.add(item)
            if link_limit is None or link_dist < link_limit:
                new_dist = link_dist + 1
                for c in cat_index[cat_index["toid"] == item].index:
                    graph_nodes.put((c, new_dist, True))

    return cat_ids, nex_ids


def subset_upstream(hydrofabric: Path, ids: "List") -> None:
    """

    Args:
        hydrofabric (_type_): _description_
        ids (List): _description_
    """
    layers = fiona.listlayers(hydrofabric)
    # Need these layers to walk the graph
    divides = gpd.read_file(hydrofabric, layer="divides")
    nexus = gpd.read_file(hydrofabric, layer="nexus")
    cat_ids, nex_ids = get_upstream_ids(divides, nexus, ids)
    # As long as these remain 1-1 this works, but that may not always be the case
    # FIXME in fact this isn't true at all, there can be catchments with no FP, and FP with no catchment
    wb_ids = list(map(lambda x: x.replace("cat", "wb"), cat_ids))

    # To use as pandas indicies, it really wants list, not set
    cat_ids = list(cat_ids)
    nex_ids = list(nex_ids)
    # Now have the index keys to subset the entire hydrofabric
    # print("Subset ids:")
    # print(cat_ids)
    # print(nex_ids)
    # print(wb_ids)
    # Useful for looking at the name of each layer and which id index is needed to subset it
    # for layer in layers:
        #     df = gpd.read_file(hydrofabric, layer=layer)
        # print(layer)
    #     print(df.head())

    flowpaths = (
        gpd.read_file(hydrofabric, layer="flowpaths")
        .set_index("id")
        .loc[wb_ids]
        .reset_index()
    )
    divides = divides.set_index("id").loc[cat_ids].reset_index()
    nexus = nexus.set_index("id").loc[nex_ids].reset_index()
    # lookup_table = gpd.read_file(hydrofabric, layer='lookup_table').set_index('id').loc[wb_ids].reset_index() v1.0???
    crosswalk = (
        gpd.read_file(hydrofabric, layer="crosswalk")
        .set_index("id")
        .loc[wb_ids]
        .reset_index()
    )  # v1.2
    flowpath_edge_list = (
        gpd.read_file(hydrofabric, layer="flowpath_edge_list")
        .set_index("id")
        .loc[nex_ids + wb_ids]
        .reset_index()
    )
    flowpath_attributes = (
        gpd.read_file(hydrofabric, layer="flowpath_attributes")
        .set_index("id")
        .loc[wb_ids]
        .reset_index()
    )
    model_attributes = (
        gpd.read_file(hydrofabric, layer="cfe_noahowp_attributes")
        .set_index("id")
        .loc[cat_ids]
        .reset_index()
    )
    # forcing_attributes = gpd.read_file(hydrofabric, layer='forcing_attributes').set_index('id').loc[cat_ids].reset_index() v1.0
    forcing_meta = (
        gpd.read_file(hydrofabric, layer="forcing_metadata")
        .set_index("id")
        .loc[cat_ids]
        .reset_index()
    )
    name = f"{ids}_upstream_subset.gpkg"

    flowpaths.to_file(name, layer="flowpaths")
    divides.to_file(name, layer="divides")
    nexus.to_file(name, layer="nexus")
    # lookup_table.to_file(name, layer="lookup_table")
    crosswalk.to_file(name, layer="crosswalk")
    flowpath_edge_list.to_file(name, layer="flowpath_edge_list")
    flowpath_attributes.to_file(name, layer="flowpath_attributes")
    model_attributes.to_file(name, layer="cfe_noahowp_attributes")
    forcing_meta.to_file(name, layer="forcing_metadata")

    # print(flowpaths)
    # print(divides)
    # print(nexus)
    # print(lookup_table)
    # print(flowpath_edge_list)
    # print(flowpath_attributes)
    # print(model_attributes)
    # print(forcing_attributes)
    make_geojson(name)


if __name__ == "__main__":
    import argparse

    # get the command line parser
    parser = argparse.ArgumentParser(description="Subset provided hydrofabric")
    parser.add_argument(
        "hydrofabric", type=Path, help="Path or link to hydrofabric geopkg to"
    )
    # TODO make this a group, pick the type of subset to do...
    # TODO allow multiple inputs for upstream?
    # TODO custom validate type to ensure it is a valid identifier?
    parser.add_argument("upstream", type=str, help="id to subset upstream from")

    args = parser.parse_args()
    subset_upstream(args.hydrofabric, args.upstream)
