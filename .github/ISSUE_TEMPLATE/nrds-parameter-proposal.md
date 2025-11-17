---
name: "Propose NRDS/NextGen Research DataStream parameter update"
about: "Submit a proposed per-catchment NRDS/NextGen parameter realization"
title: "Proposal: "
labels: "proposal, nrds, nextgen-parameters, validation-pending"
---

## Short title
Provide a brief, descriptive title (one line).

---

## Proposer information
- Name:
- GitHub handle:
- Affiliation:
- Contact:

---

## Proposal summary
Briefly describe what you're proposing and expected impact.

---

## Proposal type
- [ ] New parameter realization
- [ ] Update to existing parameters
- [ ] Hydrofabric update
- [ ] Parameter schema / tooling change
- [ ] Other: ___________

---

## Target NRDS configuration (required)
- S3 path/HydroShare URL (with details)
- Hydrofabric name & version:

---

## Catchments affected
- Catchment identifiers (comma-separated or attach file):
- Region:

---

## Files (required)
Attach or provide links:
- .parquet or .csv: 
- hydrofabric file(s) (if changed): 
- README/metadata: 
- Generation scripts/repo: 
- Evaluation artifacts: 

---

## Parameters schema (required)
List columns in your parameters file.

---

## Validation performed
- [ ] DataStreamCLI validation run (attach log)
- [ ] Schema validated
- [ ] Hydrofabric consistency checks
- [ ] Sample NRDS run performed

Attach validation logs or outputs:

---

## Evaluation & impact
- Baseline used:
- Key metrics (NSE, KGE, MAE):
- Expected community impact:

Attach evaluation plots/reports:

---

## Reproducibility (required)
- Repository URL & commit:
- Commands to generate parameters:
- Environment (conda/docker):

---

## Conflict resolution
If this overlaps with other proposals, how should conflicts be resolved?
- [ ] Use automated metrics
- [ ] Prefer recent submission
- [ ] Human review/discussion
- [ ] Other: ___________

---

## Licensing (required)
- License :
- Consent for NRDS incorporation: [Yes / No]

---

## Checklist
- [ ] Required files attached/linked
- [ ] DataStreamCLI validation run and logs included
- [ ] Reproducible steps provided
- [ ] Hydrofabric version and catchment IDs specified
- [ ] Evaluation summary included
- [ ] License and consent specified