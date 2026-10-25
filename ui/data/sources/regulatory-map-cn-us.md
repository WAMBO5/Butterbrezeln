---
schema_version: "1.0"
dataset_id: "rear-lamp-front-bumper-cn-us"
title: "Rear Lamp and Front Bumper Regulatory Mapping: China and USA"
language: "en"
assessment_date: "2026-10-25"
export_date: "2026-10-25"
jurisdictions: ["CN", "US"]
products: ["rear_lamp", "front_bumper"]
input_vehicle_category: "M1"
provenance: "Structured export of the preceding conversation answer and user-supplied specifications"
independently_reverified_for_export: false
completeness: "partial"
legal_advice: false
---

# Rear Lamp and Front Bumper Regulatory Mapping

## Dataset conventions

This file restructures the preceding answer; it is not a new legal review. Inherited dates, clause numbers, edition status and applicability conclusions have not been independently reverified for this export. Explicit gaps remain gaps; no verified compliance or approval is asserted.

- `CN` means mainland China; `US` means United States.
- Dates use `YYYY-MM-DD`; `null` means unknown, not established or not applicable, depending on the field.
- Identifiers are stable within this file and allow joins between tables.
- The framework catalog contains the named instruments from the earlier answer; inclusion does not establish applicability to every component.
- `mapped` means identified in the prior answer, not independently certified or legally validated.
- `conditional` means applicability depends on equipment, dates, vehicle classification or use.
- `verification_required` means the earlier answer did not establish a reliable designation, edition, scope or transition.
- `not_established` means no specific requirement was established in the earlier assessment; it does not mean no regulation exists.
- `assessment_reference` means an integration or screening reference, not a standalone component approval.
- The input category M1 is retained for traceability; US legal vehicle classification and each instrument's scope must be checked separately.
- Source links are embedded alongside the instruments and findings. `[cite:N]` tokens preserve the preceding research citation IDs; the URLs remain usable outside this chat.

## Product definitions

| product_id | product_type | vehicle_category_input | description | input_origin |
| --- | --- | --- | --- | --- |
| rear_lamp | Rear lamp | M1 | Exterior lighting and signalling module combining multiple light functions, lens and retro-reflector in a single housing | user_specification |
| front_bumper | Front bumper | M1 | Exterior body/trim module combining fascia, energy-management structure and integrated sensing, lighting and electronics | user_specification |

## Product functions

| function_id | product_id | function |
| --- | --- | --- |
| RL-F01 | rear_lamp | Rear position signalling: presence and visibility |
| RL-F02 | rear_lamp | Braking indication: stop lamp |
| RL-F03 | rear_lamp | Reversing illumination |
| RL-F04 | rear_lamp | Passive conspicuity: retro-reflector |
| RL-F05 | rear_lamp | Light transmission and colour definition: outer lens |
| FB-F01 | front_bumper | Styling and exterior appearance |
| FB-F02 | front_bumper | Impact and energy management: crash and pedestrian protection |
| FB-F03 | front_bumper | Sensing and driver-assistance carrier: radar, LiDAR, camera, PDC and thermal |
| FB-F04 | front_bumper | Lighting integration: signalling, decorative and functional |
| FB-F05 | front_bumper | Thermal and airflow management |
| FB-F06 | front_bumper | Feature integration: towing cover, keyless-entry aerial and EV charge port |

## Component inventory

| component_id | product_id | component | terminology_note |
| --- | --- | --- | --- |
| RL-C01 | rear_lamp | Rear position lamp | US terminology: taillamp |
| RL-C02 | rear_lamp | Stop lamp | null |
| RL-C03 | rear_lamp | Reversing lamp | US terminology: backup lamp |
| RL-C04 | rear_lamp | Outer lens | null |
| RL-C05 | rear_lamp | Retro-reflector | US terminology: reflex reflector |
| RL-C06 | rear_lamp | LED module and controller | From material and light-source description |
| RL-C07 | rear_lamp | Combined housing | Assembly-level component |
| FB-C01 | front_bumper | Cover part / fascia | null |
| FB-C02 | front_bumper | Radiator grille | null |
| FB-C03 | front_bumper | Absorber | null |
| FB-C04 | front_bumper | Lower stiffener / beam | Do not automatically classify an M1 lower stiffener as an underrun-protection device |
| FB-C05 | front_bumper | Licence-plate area / holder | Front position |
| FB-C06 | front_bumper | Towing-device cover | null |
| FB-C07 | front_bumper | Camera | Front-bumper installation |
| FB-C08 | front_bumper | Radar sensor | null |
| FB-C09 | front_bumper | Radar / LiDAR sensor including heating | Separate radar radio-frequency and LiDAR optical-safety assessments |
| FB-C10 | front_bumper | PDC / ultrasonic sensor | null |
| FB-C11 | front_bumper | Pedestrian-impact sensors | null |
| FB-C12 | front_bumper | Temperature / thermal sensor | null |
| FB-C13 | front_bumper | Decorative lighting | null |
| FB-C14 | front_bumper | Side / signalling lighting | null |
| FB-C15 | front_bumper | Keyless-entry aerial | Identify passive antenna, receiver and transmitter separately |
| FB-C16 | front_bumper | EV charge-port door / cover | User label: fuel filler cap for EVs; separate cosmetic cover from inlet, interlock and high-voltage hardware |

## Representative materials

These are user-supplied representative materials, not verified bill-of-materials declarations or proof of regulatory compliance.

| product_id | component_group | representative_materials | confirmation_status |
| --- | --- | --- | --- |
| rear_lamp | Outer lens | PMMA, red-tinted, UV-stabilised | confirm_actual_BOM |
| rear_lamp | Housing | PP or ASA/PC | confirm_actual_BOM |
| rear_lamp | Reflector surface | PC with aluminium vacuum-metallised coating | confirm_actual_BOM |
| rear_lamp | Retro-reflector | PMMA with moulded prism optics | confirm_actual_BOM |
| rear_lamp | Light source | LED modules on PCB | confirm_actual_BOM |
| rear_lamp | Seal / gasket | TPE or silicone | confirm_actual_BOM |
| rear_lamp | Fasteners / clips | PA, POM or steel | confirm_actual_BOM |
| front_bumper | Cover part / fascia | PP / PP-EPDM, talc-filled and painted | confirm_actual_BOM |
| front_bumper | Grille | PP, ABS or PC/ABS | confirm_actual_BOM |
| front_bumper | Absorber | Expanded polypropylene / EPP foam | confirm_actual_BOM |
| front_bumper | Lower stiffener / beam | Steel, aluminium or PP-GF | confirm_actual_BOM |
| front_bumper | Licence-plate holder | PP / ABS | confirm_actual_BOM |
| front_bumper | Towing-device cover | Painted PP | confirm_actual_BOM |
| front_bumper | Sensor brackets / housings | PP, PA or PA-GF | confirm_actual_BOM |
| front_bumper | Sensor lenses / radomes | PC or PMMA | confirm_actual_BOM |
| front_bumper | Lighting housings / lenses | PC lens; PP/PA housing | confirm_actual_BOM |
| front_bumper | Fasteners / clips | PA, POM or steel | confirm_actual_BOM |

## Framework catalog

The `verification_status` column describes the prior answer's evidence state, not an independently renewed verification. Links labelled as indexes or related context do not establish the full instrument text.

| framework_id | jurisdiction | designation | title_or_scope | instrument_character | verification_status | source |
| --- | --- | --- | --- | --- | --- | --- |
| CN-LS-2024 | CN | GB 5920-2024 | Light-signalling devices and systems for motor vehicles and their trailers | Mandatory national standard; function-specific transition | mapped | [CQC transition notice](https://www.cqc.com.cn/www/col68/598399.html) [cite:357]; [standard overview](https://chinastandards.org/standards/gb-5920-2024) [cite:358] |
| CN-INSTALL-2019 | CN | GB 4785-2019 | Prescription for installation of external lighting and light-signalling devices | Mandatory national standard | mapped | [SAC publication listing](https://std.sacinfo.org.cn/gnoc/queryInfo?id=18B1EB2AEBA07E051C5FAF741D10C46B) [cite:363] |
| CN-REFLECT-2024 | CN | GB 11564-2024 | Retro-reflective devices and markings for motor vehicles | Mandatory national standard; transition applies | mapped | [CQC transition notice](https://www.cqc.com.cn/www/col68/598399.html) [cite:357]; [standard overview](https://www.chinesestandard.net/PDF.aspx/GB11564-2024) [cite:355] |
| CN-ROADLIGHT-2024 | CN | GB 4599-2024 | Road illumination devices and systems for motor vehicles | Mandatory national standard; function-specific transition | mapped | [CQC transition notice](https://www.cqc.com.cn/www/col68/598399.html) [cite:357] |
| CN-LS-2019 | CN | GB 5920-2019 | Legacy rear-position / stop-lamp requirements; abbreviated scope label | Legacy national standard; transitional use | conditional | [CQC transition notice](https://www.cqc.com.cn/www/col68/598399.html) [cite:357] |
| CN-REVERSE-2007 | CN | GB 15235-2007 | Photometric characteristics of reversing lamps | Legacy national standard; transitional use | conditional | [CQC transition notice](https://www.cqc.com.cn/www/col68/598399.html) [cite:357] |
| CN-CCC | CN | CCC conformity-assessment framework | Compulsory certification / applicable self-declaration route | Conformity assessment; current product rule not established in export | conditional | [CQC transition notice](https://www.cqc.com.cn/www/col68/598399.html) [cite:357] |
| CN-BUMPER | CN | GB 17354 family; legacy GB 17354-1998 | Front and rear protective devices for passenger cars | Replacement designation and transition unresolved | verification_required | [Official replacement project record](https://std.samr.gov.cn/gb/search/gbDetailed?id=E116673EC888A3B7E05397BE0A0AC6BF) [cite:361] |
| CN-PEDESTRIAN-2024 | CN | GB 24550-2024 | Protection of motor vehicle for pedestrians in the event of a collision | Mandatory national standard | mapped | [Standard metadata](https://www.codeofchina.com/standard/GB24550-2024.html) [cite:306] |
| CN-FRONTAL-2014 | CN | GB 11551-2014 | Protection of occupants in frontal collision | Whole-vehicle reference; current edition requires confirmation | verification_required | [Related official standard context; not direct verification of this edition](https://std.samr.gov.cn/gb/search/gbDetailed?id=8531C702DB986551E05397BE0A0ACD16) [cite:309] |
| CN-PLATE-1995 | CN | GB 15741-1995 | Licence plates/brackets and their position on motor vehicles and trailers | Mandatory national standard | mapped | [Official standard record](https://openstd.samr.gov.cn/bzgk/std/newGbInfo?hcno=A535F01DC2C23BEFBE80517AAF1AE5C5) [cite:333] |
| CN-TOWING | CN | GB 32087 | Light vehicle towing devices | Screening reference; edition not established | verification_required | [Policy listing cited in prior answer; not a full standard text](https://www.ncsti.gov.cn/zcfg/zcwj/202412/P020241225536583733430.pdf) [cite:321] |
| CN-OPTICAL-2024 | CN | GB 44703-2024 | General requirements for optical radiation safety | Mandatory national standard; scope screening required | mapped | [Official standard record](https://openstd.samr.gov.cn/bzgk/std/newGbInfo?hcno=BAD778366DDDA8770924AE7B62A89D91) [cite:341] |
| CN-LASER-2024 | CN | GB/T 7247.1-2024 | Safety of laser products - Part 1: Equipment classification and requirements | Recommended national standard | mapped | [Official standard record](https://openstd.samr.gov.cn/bzgk/std/newGbInfo?hcno=2F9BB6879FC20AE55B3A49CAF7FF98E8) [cite:329] |
| CN-SUBSTANCES-2014 | CN | GB/T 30512-2014 | Requirements for prohibited substances on automobiles | Recommended national standard; mandatory status not inferred | mapped | [Standard scope](https://www.chinesestandard.us/products/gbt30512-2014) [cite:307]; [substance overview](https://www.chinesestandard.net/PDF.aspx/GBT30512-2014) [cite:308] |
| US-LIGHTING | US | FMVSS No. 108; 49 CFR 571.108 | Lamps, reflective devices, and associated equipment | Federal motor vehicle safety standard | mapped | [Regulation text](https://www.law.cornell.edu/cfr/text/49/571.108) [cite:296] |
| US-SELF-CERT | US | 49 U.S.C. 30115; self-certification framework | Manufacturer certification of compliance | Federal conformity-assessment framework | mapped | [NHTSA importer guidance](https://www.nhtsa.gov/sites/nhtsa.gov/files/best-importer-practices-final-notice-july2016.pdf) [cite:350]; [NHTSA compliance-office explanation](https://www.nhtsa.gov/sites/nhtsa.gov/files/ovsc_mission.pdf) [cite:349] |
| US-BUMPER | US | 49 CFR Part 581 | Bumper Standard | Federal bumper standard; vehicle-scope check required | mapped | [Part 581 text](https://ecfr.io/Title-49/Part-581) [cite:297] |
| US-OCCUPANT | US | FMVSS No. 208; 49 CFR 571.208 | Occupant crash protection | Federal whole-vehicle safety standard | mapped | [FMVSS index](https://www.law.cornell.edu/cfr/text/49/part-571/subpart-B) [cite:304] |
| US-REAR-VISIBILITY | US | FMVSS No. 111; 49 CFR 571.111 | Rear visibility | Federal whole-vehicle safety standard | mapped | [FMVSS index](https://www.law.cornell.edu/cfr/text/49/part-571/subpart-B) [cite:304] |
| US-AEB | US | FMVSS No. 127; 49 CFR 571.127 | Automatic emergency braking systems for light vehicles | Federal whole-vehicle system standard; timing requires check | conditional | [FMVSS index](https://www.law.cornell.edu/cfr/text/49/part-571/subpart-B) [cite:304] |
| US-LASER | US | 21 CFR 1040.10; FDA/CDRH laser-product framework | Laser products; LiDAR product code RFC | Federal laser-product framework; reporting depends on product classification | mapped | [Regulation text](https://www.ecfr.gov/current/title-21/chapter-I/subchapter-J/part-1040/section-1040.10) [cite:354]; [FDA LiDAR product classification](https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfPCD_RH/classification.cfm?PCD=RFC) [cite:344] |
| US-EV-305 | US | FMVSS No. 305; 49 CFR 571.305 | Electric-powered vehicles: electrolyte spillage and electrical shock protection | Whole-vehicle electric-powertrain safety reference | conditional | [FMVSS index](https://www.law.cornell.edu/cfr/text/49/part-571/subpart-B) [cite:304] |
| US-EV-305A | US | FMVSS No. 305a; 49 CFR 571.305a | Electric-powered vehicles: electric powertrain integrity | Successor whole-vehicle electric-powertrain safety framework | conditional | [FMVSS index](https://www.law.cornell.edu/cfr/text/49/part-571/subpart-B) [cite:304] |

## Rear-lamp mappings

Join `framework_id` to the framework catalog for designation, legal character and source URLs. The `status` column is an applicability-screening status, not a compliance result.

| mapping_id | jurisdiction | component_id_or_scope | framework_id | assessment_level | status | requirements_and_conditions |
| --- | --- | --- | --- | --- | --- | --- |
| RL-CN-001 | CN | RL-C01 | CN-LS-2024 | component | mapped | Rear-position signalling performance; transition TR-001; [cite:357][cite:358] |
| RL-CN-002 | CN | RL-C02 | CN-LS-2024 | component | conditional | Stop-lamp performance; transition TR-002; predecessor CN-LS-2019 remains relevant; [cite:357] |
| RL-CN-003 | CN | RL-C03 | CN-LS-2024 | component | conditional | Reversing-lamp performance; transition TR-002; predecessor CN-REVERSE-2007 remains relevant; [cite:357] |
| RL-CN-004 | CN | RL-C05 | CN-REFLECT-2024 | component | mapped | Passive retro-reflector performance; transition TR-001; [cite:355][cite:357] |
| RL-CN-005 | CN | RL-C04 | CN-LS-2024 | component | mapped | Finished optical-system colour and photometry; chromaticity references GB 4785; [cite:358] |
| RL-CN-006 | CN | RL-C04; RL-C05 | CN-REFLECT-2024 | component | conditional | Apply reflector requirements to lens areas providing the reflector function; [cite:355] |
| RL-CN-007 | CN | RL-C06 | CN-LS-2024 | component | mapped | Light sources, controller-dependent testing and relevant source-failure conditions; [cite:358] |
| RL-CN-008 | CN | RL-C07 | CN-LS-2024 | assembly | mapped | Assess each incorporated signalling function; [cite:358] |
| RL-CN-009 | CN | RL-C07 | CN-REFLECT-2024 | assembly | mapped | Assess the incorporated passive reflector separately; [cite:355] |
| RL-CN-010 | CN | all rear-lamp functions | CN-INSTALL-2019 | vehicle_installation | mapped | Installation of lighting and light-signalling devices; [cite:363] |
| RL-CN-011 | CN | rear_lamp assembly | CN-CCC | conformity_assessment | conditional | Determine current product-specific compulsory certification or self-declaration route; [cite:357] |
| RL-CN-012 | CN | RL-C02 | CN-LS-2019 | component | conditional | Legacy stop-lamp reference during applicable transition; [cite:357] |
| RL-CN-013 | CN | RL-C03 | CN-REVERSE-2007 | component | conditional | Legacy reversing-lamp reference during applicable transition; [cite:357] |
| RL-US-001 | US | RL-C01 | US-LIGHTING | component | mapped | S7.2; installation, visibility and activation provisions also apply; [cite:296] |
| RL-US-002 | US | RL-C02 | US-LIGHTING | component | mapped | S7.3; photometry, visibility, physical tests and combined taillamp intensity relationship; [cite:296] |
| RL-US-003 | US | RL-C03 | US-LIGHTING | component | mapped | S7.6; backup-lamp requirements; [cite:296] |
| RL-US-004 | US | RL-C05 | US-LIGHTING | component | mapped | S8.1; reflex-reflector photometry, colour and physical tests; [cite:296] |
| RL-US-005 | US | RL-C04 | US-LIGHTING | material_and_component | mapped | S14.4.1 colour; S14.1.2 / S14.4.2 plastic optical materials; weathering, transmission, haze and heat performance; [cite:296] |
| RL-US-006 | US | RL-C06 | US-LIGHTING | component | mapped | LED implementation does not replace lamp-function performance requirements; [cite:296] |
| RL-US-007 | US | RL-C07 | US-LIGHTING | assembly | mapped | S6.3; combined functions must satisfy applicable requirements and stated exceptions; [cite:296] |
| RL-US-008 | US | all rear-lamp functions | US-LIGHTING | vehicle_installation | mapped | S6 and applicable tables: number, colour, mounting, visibility, activation and combinations; [cite:296] |
| RL-US-009 | US | rear_lamp assembly | US-SELF-CERT | conformity_assessment | mapped | Manufacturer self-certification, not NHTSA pre-market type approval; [cite:350][cite:349] |

## Front-bumper mappings

| mapping_id | jurisdiction | component_id_or_scope | framework_id | assessment_level | status | requirements_and_conditions |
| --- | --- | --- | --- | --- | --- | --- |
| FB-CN-001 | CN | front_bumper assembly | CN-BUMPER | vehicle_and_assembly | verification_required | Low-speed protection; published replacement identified but final designation and transition unresolved; [cite:361] |
| FB-CN-002 | CN | FB-C01; FB-C03; FB-C04 | CN-PEDESTRIAN-2024 | whole_vehicle | mapped | Pedestrian-impact performance; M1/N1 scope subject to exclusions; [cite:306] |
| FB-CN-003 | CN | crash-energy-management structure | CN-FRONTAL-2014 | whole_vehicle | verification_required | Frontal occupant-protection integration reference; not standalone fascia or absorber approval; current edition not confirmed |
| FB-CN-004 | CN | FB-C05 | CN-PLATE-1995 | vehicle_installation | mapped | Front licence-plate bracket and position; [cite:333] |
| FB-CN-005 | CN | FB-C06 | CN-TOWING | vehicle_integration | verification_required | Screen actual towing-device accessibility and operation; edition and direct source confirmation outstanding |
| FB-CN-006 | CN | FB-C14; integrated DRL or position lamp | CN-LS-2024 | component | conditional | Classify signalling function and apply function-specific transition; [cite:357] |
| FB-CN-007 | CN | integrated lighting | CN-INSTALL-2019 | vehicle_installation | mapped | External lighting installation; [cite:363] |
| FB-CN-008 | CN | front fog or road-illumination lamp | CN-ROADLIGHT-2024 | component | conditional | Classify actual road-illumination function and transition; [cite:357] |
| FB-CN-009 | CN | FB-C13 | CN-LS-2024 | component_and_installation | conditional | Luminous-logo provisions are not blanket permission for arbitrary decorative lighting; classify actual function; [cite:358] |
| FB-CN-010 | CN | integrated plastic lighting lens | CN-LS-2024 | material_and_component | conditional | Assess within finished lighting-device requirements, not resin designation alone; [cite:358] |
| FB-CN-011 | CN | FB-C09 LiDAR | CN-OPTICAL-2024 | component | conditional | Mandatory optical-radiation-safety scope screening; effective date TR-006; [cite:341] |
| FB-CN-012 | CN | FB-C09 LiDAR | CN-LASER-2024 | component | assessment_reference | Laser classification and safety; recommended national standard; [cite:329] |
| FB-CN-013 | CN | FB-C11 | CN-PEDESTRIAN-2024 | whole_vehicle | conditional | Assess sensor operation where part of the vehicle pedestrian-protection system; [cite:306] |
| FB-US-001 | US | front_bumper assembly | US-BUMPER | whole_vehicle | conditional | Low-speed front/rear impact protection; confirm applicability under section 581.3; [cite:297] |
| FB-US-002 | US | crash-energy-management structure | US-OCCUPANT | whole_vehicle | assessment_reference | Occupant crash-protection integration; separate from Part 581 low-speed protection; [cite:304][cite:297] |
| FB-US-003 | US | FB-C05 | US-LIGHTING | vehicle_installation | not_established | S6.6.3 addresses rear holders, not a complete front-holder rule; state/jurisdictional check outstanding; [cite:296] |
| FB-US-004 | US | FB-C14; integrated DRL or position lamp | US-LIGHTING | component_and_installation | conditional | Apply actual function requirements for activation, mounting, visibility and markings; [cite:296] |
| FB-US-005 | US | front fog or road-illumination lamp | US-LIGHTING | component_and_installation | conditional | Classify function; S6.2.1 prohibits impairment of required lighting by added equipment; [cite:296] |
| FB-US-006 | US | FB-C13 | US-LIGHTING | component_and_installation | conditional | Non-impairment requirement; separate state-law check for colours and operating modes; [cite:296] |
| FB-US-007 | US | integrated plastic lighting lens | US-LIGHTING | material_and_component | conditional | S14.4.2 applies to covered plastic optical materials; [cite:296] |
| FB-US-008 | US | FB-C09 LiDAR | US-LASER | component | conditional | FDA/CDRH laser-product requirements; product code RFC; assess product and annual reporting; [cite:344][cite:354] |
| FB-US-009 | US | FB-C07; thermal camera | US-REAR-VISIBILITY | whole_vehicle | not_established | Do not assign rear-visibility standard automatically to a front camera; [cite:304] |
| FB-US-010 | US | FB-C07; FB-C08 when used for AEB | US-AEB | whole_vehicle_system | conditional | Assess integrated AEB function and implementation timing; not a passive bumper absorption standard; [cite:304] |
| FB-US-011 | US | FB-C16 charging inlet / high-voltage interface | US-EV-305 | whole_vehicle | conditional | Electric-powertrain safety assessment; cosmetic cover is distinct from charging hardware; [cite:304] |
| FB-US-012 | US | FB-C16 charging inlet / high-voltage interface | US-EV-305A | whole_vehicle | conditional | Successor electric-powertrain framework; implementation milestone TR-008 requires scope confirmation; [cite:304] |

## Cross-product materials mappings

| mapping_id | product_scope | jurisdiction | framework_id | assessment_level | status | requirements_and_conditions |
| --- | --- | --- | --- | --- | --- | --- |
| MAT-CN-001 | rear_lamp; front_bumper | CN | CN-SUBSTANCES-2014 | material | assessment_reference | Vehicles and parts; screen lead, mercury, cadmium, hexavalent chromium, PBBs and PBDEs, including limits and exemptions; do not infer standalone mandatory legal status from GB/T or an OEM specification; [cite:307][cite:308] |
| MAT-CN-002 | rear_lamp; front_bumper | CN | CN-LS-2024; CN-REFLECT-2024 | material_and_component | conditional | Finished-device optical colour and performance control; specific PMMA/PC designation alone is insufficient; [cite:358][cite:355] |
| MAT-US-001 | rear_lamp; front_bumper | US | US-LIGHTING | material_and_component | conditional | Covered optical parts: assess actual grade, colour and coating under plastic optical-material requirements; [cite:296] |
| MAT-US-002 | rear_lamp; front_bumper | US | null | material | verification_required | Complete federal and state chemical-law screen not performed; obtain formulation-level declarations for resins, pigments, coatings, solders and additives |

## Dates and transitions

These dates are transcribed from the preceding answer. Distinguish standard implementation, new component applications, existing certificate conversion and whole-vehicle approval. Applicability to a particular project requires rechecking the current instrument and transition provisions.

| transition_id | framework_id | event_scope | date | date_type | qualification | source |
| --- | --- | --- | --- | --- | --- | --- |
| TR-001 | CN-LS-2024; CN-REFLECT-2024 | New rear-position-lamp and reflector certification applications | 2025-07-01 | new_application_cutover | Function-specific CQC transition; not a universal all-function cutover | [CQC notice](https://www.cqc.com.cn/www/col68/598399.html) [cite:357] |
| TR-002 | CN-LS-2024 | New stop-lamp and reversing-lamp certification applications | 2027-01-01 | new_application_cutover | Legacy references remain relevant before cutover under applicable transition | [CQC notice](https://www.cqc.com.cn/www/col68/598399.html) [cite:357] |
| TR-003 | CN-LS-2024; CN-REFLECT-2024; CN-ROADLIGHT-2024 | Previously certified products | 2028-07-01 | certificate_conversion_deadline | Exceptions and suspension/revocation provisions apply; confirm certificate-specific scope | [CQC notice](https://www.cqc.com.cn/www/col68/598399.html) [cite:357] |
| TR-004 | CN-LS-2024 | Whole-vehicle approval | null | separate_vehicle_transition | Separate vehicle-type provisions; exact project-specific dates not supplied | [Standard overview](https://chinastandards.org/standards/gb-5920-2024) [cite:358] |
| TR-005 | CN-PEDESTRIAN-2024 | GB 24550-2024 implementation | 2025-01-01 | implementation_date | Confirm vehicle exclusions and all applicable transition clauses | [Standard metadata](https://www.codeofchina.com/standard/GB24550-2024.html) [cite:306] |
| TR-006 | CN-OPTICAL-2024 | GB 44703-2024 implementation | 2026-10-01 | implementation_date | Screen actual laser/optical product scope | [Official standard record](https://openstd.samr.gov.cn/bzgk/std/newGbInfo?hcno=BAD778366DDDA8770924AE7B62A89D91) [cite:341] |
| TR-007 | CN-LASER-2024 | GB/T 7247.1-2024 implementation | 2025-04-01 | implementation_date | Recommended standard; legal effect depends on applicable requirements | [Official standard listing](https://openstd.samr.gov.cn/bzgk/std/std_list?p.p1=0&p.p2=GB/T7247.1-2024) [cite:328] |
| TR-008 | US-EV-305A | Beginning of mandatory applicability identified in prior answer | 2027-09-01 | mandatory_applicability_milestone | Confirm vehicle scope, exceptions and current amendments before relying on date | [FMVSS index](https://www.law.cornell.edu/cfr/text/49/part-571/subpart-B) [cite:304] |

## Conformity and design caveats

| note_id | product_scope | jurisdiction | topic | finding_or_action | evidence |
| --- | --- | --- | --- | --- | --- |
| NOTE-001 | rear_lamp | CN; US | Red outer lens | A representative red-tinted lens cannot be assumed suitable for every optical path; reversing-lamp colour and photometry must be met | CN-LS-2024; US-LIGHTING [cite:358][cite:296] |
| NOTE-002 | rear_lamp | US | DOT terminology | Do not specify a government-issued DOT product approval; NHTSA does not approve these products | [NHTSA explanation](https://www.nhtsa.gov/sites/nhtsa.gov/files/ovsc_mission.pdf) [cite:349] |
| NOTE-003 | rear_lamp | US | DOT marking | Prior answer identifies DOT marking as optional for ordinary non-headlamp lamps and reflective devices covered by S6.5.1.2; verify actual product classification | US-LIGHTING [cite:296] |
| NOTE-004 | rear_lamp | CN | October 2026 transition | Do not replace every legacy standard solely because a 2024 standard has a 2025 implementation date; stop/reversing functions have separate new-application timing | CN-LS-2024; TR-002 [cite:357] |
| NOTE-005 | front_bumper | CN; US | Assessment granularity | Maintain separate records for impact protection, lighting, radio, optical safety, sensors and charging hardware | Dataset recommendation; not a sourced legal rule |
| NOTE-006 | front_bumper | CN; US | Lower-stiffener terminology | Describe actual pedestrian leg support or reinforcement function; do not automatically label it an underrun-protection device | Specification clarification; classification requires review |
| NOTE-007 | front_bumper | CN; US | Charge-port terminology | Separate charge-port door/cover from inlet, interlock and high-voltage components | Specification clarification |
| NOTE-008 | front_bumper | US | Passive pedestrian protection versus AEB | FMVSS No. 127 addresses AEB rather than passive bumper energy absorption | US-AEB [cite:304] |
| NOTE-009 | front_bumper | US | Front camera versus rear visibility | Camera presence alone does not establish FMVSS No. 111 applicability to a front-bumper camera | US-REAR-VISIBILITY [cite:304] |
| NOTE-010 | rear_lamp; front_bumper | CN | GB/T legal character | Do not equate a recommended national standard or OEM contractual reference with a standalone mandatory law | CN-SUBSTANCES-2014 [cite:307]; CN-LASER-2024 [cite:329] |

## Verification gaps

The following rows preserve unresolved items. An absent framework identifier is an intentional missing value, not evidence that the component is unregulated.

| gap_id | jurisdiction | component_or_scope | topic | status | required_action | prior_evidence_state |
| --- | --- | --- | --- | --- | --- | --- |
| GAP-001 | CN | front_bumper | Bumper standard | verification_required | Confirm replacement designation, effective edition and transition for GB 17354 family | Official project identifies a replacement; [cite:361] |
| GAP-002 | CN | front_bumper fascia / grille | Exterior projections | verification_required | Identify applicable standard, edition and clauses | Not conclusively established in prior assessment |
| GAP-003 | US | front_bumper fascia / grille | Exterior projections | not_established | Determine applicable federal and state provisions rather than assuming direct equivalence | No directly corresponding general framework verified |
| GAP-004 | CN | radar | Radio authorization | verification_required | Determine operating band, transmitter configuration, authorization route and current Chinese instrument | Precise instrument not verified |
| GAP-005 | US | radar | Radio authorization | verification_required | Determine operating band, transmitter configuration and applicable authorization route | Precise instrument not verified |
| GAP-006 | CN; US | electronic subassemblies / complete vehicle | EMC | verification_required | Determine applicable component/vehicle EMC requirements and evidence | Complete EMC assessment outstanding |
| GAP-007 | CN | camera / thermal camera | Function-specific regulation | not_established | Determine actual vehicle function and corresponding requirements | No blanket standalone front-camera approval established |
| GAP-008 | CN | radar / camera used for AEB | AEB | verification_required | Determine applicable vehicle-level driver-assistance requirements and dates | Complete Chinese AEB assessment not established |
| GAP-009 | US | radar / camera used for AEB | AEB implementation timing | verification_required | Check FMVSS No. 127 timing, scope and current amendments | US-AEB identified; timing not established |
| GAP-010 | CN; US | PDC / ultrasonic sensor | Standalone versus integrated requirements | not_established | Assess actual parking-assistance function and integration | No standalone mandatory component standard verified |
| GAP-011 | US | pedestrian-impact sensors | Protection-system classification | not_established | Determine actual system and applicable requirements | Sensor label alone does not establish FMVSS applicability |
| GAP-012 | CN; US | keyless-entry aerial | Radio-system classification | verification_required | Distinguish passive antenna, receiver and transmitter, then classify | No precise framework assigned |
| GAP-013 | CN; US | temperature sensor / sensor heater | Electrical and thermal integration | not_established | Retain electrical, thermal and system-safety checks | No separate component-specific rule verified |
| GAP-014 | US | towing-device cover | Cover and vehicle interaction | not_established | Assess effect on applicable bumper and vehicle requirements | No separate towing-cover standard verified |
| GAP-015 | CN | charge port / EV electrical system | Charging and EV safety | verification_required | Identify Chinese inlet, charging-interface and vehicle electrical-safety requirements | Not sufficiently verified |
| GAP-016 | US | charge port / EV electrical system | FMVSS 305 / 305a transition | verification_required | Confirm actual vehicle scope, dates and applicable amended text | Do not apply whole-vehicle standard to cosmetic cover automatically |
| GAP-017 | US | front licence-plate holder | State / jurisdictional requirements | verification_required | Check intended registration jurisdictions and front-plate installation rules | FMVSS 108 rear-holder provision is not a complete front-holder rule; [cite:296] |
| GAP-018 | US | decorative lighting | State equipment / use laws | verification_required | Check colours, operating modes and road-use restrictions | Federal non-impairment screen alone is incomplete |
| GAP-019 | US | both products and all materials | Chemical restrictions | verification_required | Complete federal/state screen and formulation-level declarations | No complete US chemical-law assessment performed |
| GAP-020 | CN | frontal crash integration | GB 11551 edition | verification_required | Verify current edition and applicability from direct authoritative text | Prior answer cited related context, not direct edition confirmation |
| GAP-021 | CN | towing device / cover | GB 32087 edition and scope | verification_required | Verify designation, current edition and cover-related implications | Screening reference only |
| GAP-022 | CN | rear_lamp | CCC product-specific rules | verification_required | Identify current rule version, catalogue coverage and certification/self-declaration route | General conformity-assessment reference only |
| GAP-023 | CN; US | both products | Actual vehicle and approval dates | verification_required | Capture legal vehicle class, intended production dates, approval history and actual BOM | Input M1 and representative materials are insufficient for final applicability |

## Recommended evidence fields

These are proposed data-model fields, not statements that the corresponding evidence has already been obtained.

| field_name | data_type | purpose |
| --- | --- | --- |
| requirement_record_id | string | Stable unique identifier |
| product_id | string | Join to product definition |
| component_id | string or null | Join to component inventory |
| jurisdiction | enum: CN / US | Market |
| legal_vehicle_class | string or null | Actual classification under the target instrument |
| framework_id | string or null | Join to framework catalog |
| designation_and_edition | string or null | Exact legal or standards identifier |
| clause | string or null | Applicable provision |
| assessment_level | enum | Material, component, assembly, vehicle installation, whole vehicle or system |
| applicability_trigger | string | Equipment, function, band, date or other condition |
| approval_or_manufacture_date | ISO 8601 date or null | Determine transition applicability |
| transition_id | string or null | Join to date/transition record |
| required_evidence | array of strings | Test report, certificate, self-certification, declaration or installation assessment |
| evidence_document_id | string or null | Actual evidence reference |
| applicability_status | enum | Applicable, conditional, not applicable or verification required |
| compliance_status | enum | Not assessed, evidence pending, conforming or nonconforming |
| source_url | string or null | Externally usable source link |
| last_verified_date | ISO 8601 date or null | Actual verification date; do not substitute export date |
| review_notes | string or null | Limitations and unresolved matters |
