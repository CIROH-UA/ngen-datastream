This document describes which NextGen models you are able to run via NGIAB and `ngen-datastream`.

NextGen is a framework in which physical models can be coupled in numerical simulations via the Basic Model Interface (BMI). NextGen in a Box (NGIAB) is a docker container which contains many pre-built models. `ngen-datastream` only has knowledge of models that are available in NGIAB. For example, models like the Conceptual Functional Equivalent (CFE) Model are available, but the particular model you are interested in running may not yet be integrated in NGIAB. Even if it is, `ngen-datastream` may not yet support the model.  Start an issue to include your model if it is not in the lists below.

## NextGen Models Available via `ngen-datastream`
* [SLoTH](https://github.com/NOAA-OWP/SLoTH)
* [CFE](https://github.com/NOAA-OWP/cfe)
* [PET](https://github.com/NOAA-OWP/evapotranspiration)
* [Noah-OWP-Modular](https://github.com/NOAA-OWP/noah-owp-modular)
* [t-route](https://github.com/NOAA-OWP/t-route)

## NextGen Models Available in NGIAB and coming soon to `ngen-datastream`
* [SoilFreezeThaw](https://github.com/NOAA-OWP/SoilFreezeThaw)
* [SoilMoistureProfiles](https://github.com/NOAA-OWP/SoilMoistureProfiles)
* [TOPMODEL](https://github.com/NOAA-OWP/topmodel)
* [LSTM](https://github.com/NOAA-OWP/lstm)
  
## Coming Soon to NGIAB and `ngen-datastream`
* [Sac-SMA](https://github.com/NOAA-OWP/sac-sma)
* [Snow17](https://github.com/NOAA-OWP/snow17)
* [LGAR](https://github.com/NOAA-OWP/LGAR-C)

