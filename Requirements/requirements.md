# Hackathon Project Requirements: CT Patient Companion Ecosystem

## Document scope and source

This document consolidates the eight supplied Siemens Healthineers slide photographs in their printed page order, **pages 2–9**. It covers the companion architecture and five functional challenges for a CT imaging workflow.

Requirements and numerical limits below come from the slides. Requirement IDs are editorial additions for reference. Architecture descriptions are context, not an assertion that teams must implement every existing component. Items absent from the slides are listed separately as open questions.

The source slides carry a **Restricted © Siemens Healthineers** marking.

## 1. Capability overview — Page 2

The companion supports context understanding and communication throughout the patient workflow.

| Capability | Intended behavior | Illustrative statement from the slide |
| --- | --- | --- |
| Movement sensor and guide | Detect patients approaching and moving, and guide them accordingly. | “Now someone is in front of me.” |
| Helpdesk | Answer patient questions. | “The exam will take 10 minutes.” |
| Patient identifier | Identify the patient throughout the workflow. | “This is still the same person.” |
| Room status checker | Check the status of the CT examination room. | “No one else is in the room.” |
| Positioning sensor and guide | Recognize the patient’s position on the table and provide guidance. | “The patient is lying headfirst.” |

These statements illustrate capabilities; the examination duration is an example, not a fixed requirement.

## 2. Companion ecosystem — Page 3

### 2.1 Components and technology context

| Component | Role | Technologies shown |
| --- | --- | --- |
| ACU App | Operator interface that sends commands and workflows. | Browser/PWA, React, REST |
| ACU Server | Integration and communication hub; API Gateway. | ASP.NET Core, WebSocket and REST, Docker on Linux |
| Robot / KettyBot App | Patient companion interface. | Kotlin / React Native |

### 2.2 Communication flow

- Commands travel from the ACU App through the REST API to the ACU Server, then through WebSocket and REST to the Ketty Bot Pro.
- Status and telemetry return through the same platform.
- The robot supplies telemetry/status to the server; the server supplies telemetry to the operator application.

## 3. Component view — Page 4

The ACU server hardware hosts a local application and service platform. A single API Gateway provides unified ingress and service access.

| Layer or group | Components shown |
| --- | --- |
| User touchpoints | ACU, workstation, waiting cabin |
| Interfaces | ACU UI web app, Cabin web app |
| Domain services | Room Status Checker, Patient Validator, Patient Health Calculator, Patient Movement Detector |
| Image sources | BOT and camera |
| Data and outputs | Room status, patient data, additional data storage and outputs |

The architecture emphasizes a **single gateway, modular services, and local processing**.

The Patient Health Calculator appears in the component diagram, but no detailed requirements for that service are provided in the supplied pages. The diagram also contains an unlabeled data store; no purpose is assigned to it here.

## 4. Continuous Patient Detection and Guidance — Page 5

### Objective

Ensure that the correct patient is detected and continuously guided throughout the workflow.

### Functional requirements

| ID | Requirement |
| --- | --- |
| CDG-01 | Receive patient images from the BOT through the API Gateway/backend to register the patient. |
| CDG-02 | Identify the patient on the ACU and verify that guidance remains continuous. |
| CDG-03 | If the patient is lost, notify the ACU and trigger corrective guidance. |

### Constraints

| Constraint | Stated limit |
| --- | --- |
| Memory | **Less than 2 GB** |
| Stored patients | **Latest 2 patients** |
| Feedback time | **At most 3 seconds** |
| Execution location | **Local ACU** |

The slide does not define the start and end events used to measure the feedback time.

## 5. Helpdesk — Page 6

### Objective

Answer general patient questions and provide clear context so that the patient feels prepared and ready for the scan.

### Functional requirements

| ID | Requirement |
| --- | --- |
| HD-01 | Capture the patient’s question through the BOT and send it through the API Gateway/backend. |
| HD-02 | Run the model on the ACU to generate an appropriate response. |
| HD-03 | Return the ACU output to the BOT for patient-facing output. |
| HD-04 | Use the BOT only for input and display; execute the model locally on the ACU. |

**Source note:** The “Respond” box ends with “ACU output is returned to the BOT for” and does not complete the sentence. Patient-facing output is inferred from the helpdesk objective and the “BOT only — Input/display” constraint.

### Constraints

| Constraint | Stated limit |
| --- | --- |
| Memory | **4 GB** |
| Storage | **4 GB** |
| Model execution | **Local ACU** |
| BOT role | **Input/display only** |

No response-time target, supported language list, or knowledge-source specification is given.

## 6. Patient Identification to Ensure the Right Patient Is Scanned — Page 7

### Objective

The scan workflow must not start until the registered patient has been successfully identified and confirmed.

### Identification mechanisms

| Mechanism | Description |
| --- | --- |
| Face | Image-based matching |
| QR code | Registered code |
| Voice | Voice verification |

The slide lists all three mechanisms but does not specify whether they are alternatives or must be combined.

### Functional requirements

| ID | Requirement |
| --- | --- |
| PI-01 | Capture patient information on the BOT and send it to the ACU. |
| PI-02 | Execute identification locally on the ACU. |
| PI-03 | Allow the user to accept or reject the identification result. |
| PI-04 | Release the workflow only after successful identification and confirmation. |
| PI-05 | If identification fails, request re-identification, allow a maximum of 3 attempts, and keep the workflow blocked. |

### Constraints and workflow gate

| Constraint | Stated limit or behavior |
| --- | --- |
| Execution location | **Local ACU** |
| Memory | **Less than 2 GB** |
| Patient retention | **Latest 5 patients only** |
| Retry limit | **Maximum 3 attempts** |
| Confirmation | **User acceptance/rejection** |
| Workflow release | **Only after confirmation** |

The slide does not specify who performs confirmation, whether the initial attempt counts toward the three-attempt limit, or what escalation follows exhaustion of the attempts.

## 7. CT Exam Room Readiness Checker — Page 8

### Objective

Detect unexpected objects, incomplete preparation, or other deviations that require attention before the imaging workflow starts.

### Functional requirements

| ID | Requirement |
| --- | --- |
| RR-01 | Perform the readiness check on an **empty room only**. |
| RR-02 | Receive multiple room images from the BOT through the API Gateway/backend. |
| RR-03 | Analyze the images on the ACU using a room-readiness algorithm, taking expected equipment into account. |
| RR-04 | Detect deviations, including unknown or unexpected objects. |
| RR-05 | Return a **ready/not ready** room status to the ACU UI. |
| RR-06 | Allow workflow start when the room is ready; block scan start when it is not ready. |
| RR-07 | Support preparation/correction and a BOT re-check after objects are cleared. |
| RR-08 | Store relevant images locally. |

### Decision and correction flow

1. Capture room images and evaluate readiness.
2. If ready, allow the workflow to proceed.
3. If not ready, block the scan and prepare/correct the room.
4. Clear unexpected objects and have the BOT re-check the room.
5. Store relevant images locally.

### Constraints

| Constraint | Stated limit or scope |
| --- | --- |
| Memory | **4 GB** |
| Storage | **2 GB** |
| Room occupancy | **Empty room only** |
| Image input | **Multiple BOT images** |
| Image storage | **Local** |

The expected-equipment inventory, image-retention policy, and precise readiness criteria are not specified.

## 8. Patient Positioning Recognition and Guidance — Page 9

### Objective

Detect patient movement or deviations from the expected position that require correction before scanning begins.

### Functional requirements

| ID | Requirement |
| --- | --- |
| PP-01 | Generate a reference map of the expected patient position. |
| PP-02 | Receive camera images and continuously track patient movement. |
| PP-03 | Compare the detected position with acceptable criteria. |
| PP-04 | Notify the ACU when action is required. |
| PP-05 | Guide patient repositioning and block workflow start when needed. |
| PP-06 | Allow workflow start when the position is within the acceptable criteria. |

### Workflow decision

| Position assessment | Required behavior |
| --- | --- |
| Within criteria | Allow workflow start. |
| Outside criteria | Guide repositioning and block start. |

### Constraints

| Constraint | Stated limit or behavior |
| --- | --- |
| Execution | **Local edge execution** |
| Memory | **4 GB** |
| Storage | **2 GB** |
| Monitoring | **Continuous** |
| Reference | **Expected-position map** |
| Notification destination | **ACU** |

The illustration shows a ceiling camera. The slide does not define camera specifications, acceptable movement/position thresholds, or how the reference map is obtained.

## 9. Consolidated resource and behavior limits

Limits are listed per capability. The slides do not state whether the memory and storage budgets are shared across services, nor whether the unqualified 4 GB and 2 GB values are strict maxima.

| Capability | Page | Memory | Storage | Other limits |
| --- | --- | --- | --- | --- |
| Continuous detection and guidance | 5 | < 2 GB | Not specified | Latest 2 patients; feedback ≤ 3 seconds; local ACU |
| Helpdesk | 6 | 4 GB | 4 GB | Model runs on local ACU; BOT input/display only |
| Patient identification | 7 | < 2 GB | Not specified | Latest 5 patients; maximum 3 attempts; user confirmation; local ACU |
| Room readiness | 8 | 4 GB | 2 GB | Empty room only; multiple BOT images; store relevant images locally |
| Positioning recognition and guidance | 9 | 4 GB | 2 GB | Local edge execution; continuous monitoring; ACU notification |

**Keep the retention limits separate:** continuous detection retains the latest **2** patients, whereas patient identification retains the latest **5** patients.

## 10. Details requiring organizer clarification

The following are documentation gaps, not additional requirements:

- Whether teams must implement one selected challenge or all five.
- Required submission artifacts, repository format, demo expectations, deadlines, and judging criteria.
- Available hardware, datasets, pretrained models, reference images, and sample patient registrations.
- API endpoints, payload schemas, authentication, event formats, and integration test environment.
- Whether resource budgets are per process, per service, or shared; how resource usage will be measured.
- Accuracy targets, confidence thresholds, latency targets beyond the page 5 feedback limit, and failure-handling rules.
- Identification modality selection, confirmation actor, retry counting, and escalation after failed attempts.
- Exact retention/deletion rules for patient data and locally stored room images.
- Readiness criteria, expected-equipment lists, and acceptable positioning/movement tolerances.

## Appendix: Source page mapping

| Printed page | Slide title |
| --- | --- |
| 2 | Capabilities for context understanding and communication |
| 3 | The companion ecosystem |
| 4 | Component View |
| 5 | Continuous Patient Detection & Guidance |
| 6 | Helpdesk |
| 7 | Patient Identification to Ensure the Right Patient Is Scanned |
| 8 | CT Exam Room Readiness checker |
| 9 | Patient Positioning Recognition & guide |

