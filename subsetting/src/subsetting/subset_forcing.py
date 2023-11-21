import argparse, os, json


def main():
    """
    Find forcing files in a directory that match the catchments within a catchment.geojson

    """
    # setup the argument parser
    parser = argparse.ArgumentParser()
    parser.add_argument(dest="forcing_dir", type=str, help="Path to forcing files")
    parser.add_argument(
        dest="forcing_dir_out", type=str, help="Path to output the forcing files subset"
    )
    parser.add_argument(
        dest="catchment_file", type=str, help="A catchment geojson file"
    )
    args = parser.parse_args()

    indir = args.forcing_dir
    outdir = args.forcing_dir_out
    catch_file = args.catchment_file

    if not os.path.exists(outdir):
        os.system(f"mkdir {outdir}")

    forcing_files = os.listdir(indir)

    print("Reading catchment data...")
    with open(catch_file) as fp:
        data = json.load(fp)

        # User should validate the catch file.
        # Would do here with ngen-cal, just don't want to create the dependency
        feats = data["features"]
        forcing_out = []
        for jfeat in feats:
            found = False
            try:  # Geopandas/pydantic descrepancy
                cat_id = jfeat["id"]
            except:
                cat_id = jfeat["properties"]["id"]
            for jforcing in forcing_files:
                if jforcing.find(cat_id) >= 0:
                    found = True
                    forcing_out.append(jforcing)
                    os.system(
                        f"cp {os.path.join(indir,jforcing)} {os.path.join(outdir,jforcing)}"
                    )
            if not found:
                print(f"Couldn't find forcing file for {cat_id}!")
            else:
                print(f"Found forcing file for {cat_id}!")


if __name__ == "__main__":
    main()
