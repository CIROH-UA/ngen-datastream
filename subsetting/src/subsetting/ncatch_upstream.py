import geopandas as gpd
import argparse, os
from subset import get_upstream_ids


def main():
    # setup the argument parser
    parser = argparse.ArgumentParser()
    parser.add_argument(
        dest="infile", type=str, help="A gpkg file containing divides and nexus layers"
    )
    parser.add_argument(
        dest="outfile",
        type=str,
        help="A text file containing the number of upstream catchments for each catchment",
    )
    args = parser.parse_args()

    infile = args.infile
    outfile = args.outfile

    print("Reading catchment data...")
    df_cat = gpd.read_file(str(infile), layer="divides")

    print("Reading nexus data...")
    df_nex = gpd.read_file(str(infile), layer="nexus")

    df_cat.set_index("id", inplace=True)

    print("Finding upstream catchments...")
    upstream = nupstream(df_cat.reset_index(), df_nex.reset_index(), df_cat.index)

    with open(outfile, "w") as fp:
        fp.write(
            f"Catchment IDs and the number of upstream catchments\nGenerated with file {os.path.basename(infile)}\n"
        )
        for jcatch in upstream:
            fp.write(f"{jcatch} : {upstream[jcatch]}\n")

    print(f"Done!  - >  {outfile}")


def nupstream(divides, nexus, cat_list):
    """
    Find the number of upstream catchments for each catchment
    """
    upstream = {}
    for j in range(len(cat_list)):
        jcat_id = cat_list[j]
        cat_up_ids, nexus_up_ids = get_upstream_ids(divides, nexus, jcat_id)
        jnupstream = len(cat_up_ids)
        upstream[jcat_id] = jnupstream

    upstream = dict(sorted(upstream.items(), key=lambda x: x[1], reverse=True))

    return upstream


if __name__ == "__main__":
    main()
