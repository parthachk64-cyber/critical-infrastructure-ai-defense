# Policy map (explanatory)

Relates concrete outputs of this repository to published guidance. **A passing synthetic test certifies nothing about compliance or field readiness.** Mappings are explanatory; they do not claim that the software implements any outcome.

Sources, checked 2026-11-25 from official copies:

* **NIST CSF 2.0** - *The NIST Cybersecurity Framework (CSF) 2.0*, NIST CSWP 29, February 26, 2024 (<https://nvlpubs.nist.gov/nistpubs/CSWP/NIST.CSWP.29.pdf>). Category and subcategory wording below is quoted from that text.
* **NIST SP 800-82 Rev. 3** - *Guide to Operational Technology (OT) Security*, September 2023, DOI [10.6028/NIST.SP.800-82r3](https://doi.org/10.6028/NIST.SP.800-82r3). Section numbers and titles below are from its table of contents (PDF read).

## Output -> CSF 2.0 outcome

| repository output | CSF 2.0 outcome (verbatim text) | explanation |
|---|---|---|
| coverage and data-quality report (`window_missing_fraction`, data-quality cases, `data-check`) | **DE.CM** Continuous Monitoring: "Assets are monitored to find anomalies, indicators of compromise, and other potentially adverse events" | shows which assets/sensors were observed and where observation lapsed |
| timestamped detection with evidence ids and reason (alert groups, cases) | **DE.AE** Adverse Event Analysis: "Anomalies, indicators of compromise, and other potentially adverse events are analyzed to characterize the events and detect cybersecurity incidents"; **DE.AE-03** "Information is correlated from multiple sources" | corroboration across assets is a small analogue of DE.AE-03 |
| review case with disposition and reviewer decision time | **RS.MA-02** "Incident reports are triaged and validated"; **RS.MA-03** "Incidents are categorized and prioritized" | triage cases separate observed, inferred and reviewed fields |
| trace JSON recording what was examined and decided | **RS.AN-06** "Actions performed during an investigation are recorded, and the records' integrity and provenance are preserved" | records exist; integrity protection beyond checksums is not implemented |
| (not implemented) restoration | **RC.RP-01** "The recovery portion of the incident response plan is executed once initiated from the incident response process" | no recovery function exists here; a recovery note would be a human-authored record |

## Output -> SP 800-82 Rev. 3 sections

| repository output | SP 800-82r3 section (title as in the TOC) | explanation |
|---|---|---|
| maintenance windows as context for triage | 3.3.7 *Develop a Maintenance Tracking Capability*; 6.2.5 *Maintenance (PR.MA)* | planned work is recorded so that unusual readings can be interpreted, not ignored |
| review cases and advisory actions | 3.3.8 *Develop an Incident Response Capability* | cases feed a response process; this repo performs no response |
| recovery note (human-authored, not generated) | 3.3.9 *Develop a Recovery and Restoration Capability*; 6.5.1 *Recovery Planning (RC.RP)* | outside software scope |
| anomaly scoring and alert grouping | 6.3.1 *Anomalies and Events (DE.AE)*; 6.3.2 *Security Continuous Monitoring (DE.CM)* | Section 6 of Rev. 3 uses the earlier CSF 1.1-style categories (e.g. DE.DP also appears), so the identifiers differ from CSF 2.0 above |
| continuous review of data and risk | 4.1.4 *Monitoring Risk in an OT Environment* | the demo has no risk-management process |

## Historical versus later guidance

CSF 2.0 (Feb 2024) and SP 800-82r3 (Sep 2023) were published **after** the May 2021 Colonial Pipeline incident; SP 800-82 Rev. 2 (2015) was the revision current at that time. This map describes outcomes in current guidance and does not claim they governed the 2021 events.

## Binding obligations: not asserted

No binding legal obligation is claimed. The article's reference list includes CISA's CIRCIA fact sheet (2022) and an EU NIS 2 directive entry, and the Colonial case involved TSA's pipeline security program (CRS IN11667), but sector, jurisdiction, effective dates and official authority for any specific requirement were **not verified in this build**. Before citing a requirement, confirm it against the official regulatory text and effective date.
