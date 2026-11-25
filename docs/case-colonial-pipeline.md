# Case record: Colonial Pipeline ransomware incident (May 2021)

A short, source-bound record. It has **no retrospective alerts and no validation labels**, and it cannot show that any model would have prevented or shortened the incident.

## Sources and how each was read

| source | status in this build |
|---|---|
| GAO-21-105263, *Critical Infrastructure Protection: TSA Is Taking Steps to Address Some Pipeline Security Program Weaknesses* (testimony, 27 July 2021) - <https://www.gao.gov/assets/gao-21-105263.pdf> | **Not read directly.** Every automated request to gao.gov returned HTTP 403 (Access Denied), including the product page and PDF. The GAO statements below come from a web-search summary of that testimony and are marked *via search summary*. Re-verify against the PDF before quoting. |
| CRS Insight IN11667, *Colonial Pipeline: The DarkSide Strikes* (Congressional Research Service, 11 May 2021) - <https://www.congress.gov/crs_external_products/IN/PDF/IN11667/IN11667.2.pdf> | **Read in full text** (first two pages). Used as a second official source because the GAO text was unreachable; it is a CRS product, not GAO. |

## What the sources say

| fact | source | status |
|---|---|---|
| On 8 May 2021 Colonial Pipeline Company announced it had halted its pipeline operations due to a ransomware attack | CRS IN11667, p. 1 | read |
| The disruption affected supplies of gasoline and other refined products across the East Coast | CRS IN11667, p. 1 | read |
| The ransomware was the DarkSide ransomware-as-a-service variant | CRS IN11667, p. 1 | read |
| Malicious actors used DarkSide ransomware in a cyberattack on Colonial's **information technology network** | GAO-21-105263 | via search summary |
| The company then **disconnected certain systems that monitor and control physical pipeline functions** so that they would not be compromised | GAO-21-105263 | via search summary |
| An earlier (2020) pipeline ransomware attack also led to a shutdown; 2018 attacks disrupted customer-communication systems (not pipeline operations) at four gas pipeline companies | CRS IN11667, p. 1 | read |
| TSA administers the federal pipeline security program | CRS IN11667, p. 2 | read |

## Separating what is documented

* **Affected business IT:** the IT network (GAO via summary; CRS describes a ransomware attack on the company).
* **Operator's decision:** to halt pipeline operations (announced 8 May 2021, CRS) and to disconnect systems that monitor and control physical functions (GAO via summary), described by GAO as done so those systems "would not be compromised".
* **Resulting operational disruption:** a pipeline shutdown and East Coast fuel-supply disruption (CRS).
* **Not established by these sources:** that industrial controllers were directly compromised. The sources read describe precautionary disconnection, not a confirmed compromise of OT. This record makes no claim either way.
* **Not established:** the exact timeline of intrusion, detection and restoration, anything about Colonial's internal telemetry, and whether earlier alerts existed. None is invented here.

## What telemetry and review decisions would be relevant (discussion, not validation)

* **Visibility continuity.** When monitoring links are disconnected on purpose, the operator loses observations. The demo's missing-sensor example shows that gap should surface as a *data-quality* case (`telemetry_quality_check`), distinct from an anomaly, so a reviewer knows scores for that asset are less reliable.
* **Corroboration across the IT/OT boundary.** The incident began on business IT. Evidence relevant to a decision to isolate OT would come from IT-side telemetry that this OT-sensor demo does not model; connecting them is out of scope here.
* **Review decisions with recorded timestamps.** A decision to halt operations is a business and safety decision. The repository's analogue is a reviewer disposition (`review_requested`, `observation_continued`, `escalation_recorded`...) with the evidence ids and decision time attached, kept separate from the model's score. It is advisory and issues no command.
* **Maintenance vs incident.** Planned work can look like an incident in sensor data; the demo records maintenance context next to the anomaly (see examples 2 and 5).

None of this shows a model "would have caught" the incident. Any claim of that kind would need real telemetry, labels set without hindsight, and a pre-registered protocol, none of which exists here.
