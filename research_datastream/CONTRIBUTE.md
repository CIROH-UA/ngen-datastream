The current configuration of the NextGen Research DataStream exists [here](https://github.com/CIROH-UA/ngen-datastream/blob/main/research_datastream/configuration/CONUS/realization_sloth_nom_cfe_pet_troute.json). This file is picked up directly during the NextGen executions in AWS Cloud. By editting the realization file in this repository, the daily NextGen forecasts can be improved.

To contribute to this realization file follow these steps.
1) Clone this repository and create a new branch
2) Edit the CONUS realization file with your improvements
3) Create a pull request and ensure all tests pass
At this point, an automated process will commence that evaluates your NextGen configuration and merges the pull request.
