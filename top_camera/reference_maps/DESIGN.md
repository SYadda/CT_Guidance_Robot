# Overhead-camera CT patient positioning reference maps v1

[Chinese / 中文](DESIGN_ZH.md)

Design date: 2026-10-24. Scope: two common arm positions for adults undergoing routine supine CT. The illustration files remain design assets. Their arm-position relationships are now implemented in `positioning.py`, selected through `criteria.json`; illustration pixel coordinates are not used as acceptance thresholds.

## Medical basis and scope

1. **Routine head CT:** AAPM's *Adult Routine Head CT Protocols* v2.0 (2016) describes supine, head-first positioning, use of a head holder when possible, and protocol-specific head/neck alignment to reduce lens exposure. Newcastle Hospitals also describes supine positioning with a headrest. Arms alongside the body are supported by section E.1.2 of the SNM *Procedure Guideline for SPECT/CT Imaging 1.0* (2006). That recommendation comes from SPECT/CT and supplements the arm-position design; other nuclear medicine workflow requirements are not generalized to all diagnostic CT.
2. **Routine chest/abdomen/pelvis CT:** AAPM's *Adult Routine Chest-Abdomen-Pelvis CT Protocols* v1.0 (2014) explicitly describes supine positioning with arms above the head. UCSF explains that placing the arms overhead reduces arm-related image artifacts.
3. **Exceptions:** The ESER 2020 polytrauma guideline (Table 9) makes arm positioning dependent on the patient's condition. Stable patients undergoing trunk CT generally have their arms elevated, with exceptions including significant shoulder-region injuries. These trauma recommendations do not define one workflow for all patients. Inability to raise the arms, pain, injury, a single lowered arm, or a special examination requires technologist assessment and an appropriate protocol; do not automatically switch to the other routine reference map.

Sources:

- [AAPM routine head CT (2016)](https://aapm.org/pubs/CTProtocols/documents/AdultRoutineHeadCT.pdf)
- [Newcastle Hospitals: CT head scan](https://www.newcastle-hospitals.nhs.uk/services/radiology/ct-scans/ct-head-scan/)
- [SNM SPECT/CT guideline (2006), E.1.2](https://jnm.snmjournals.org/content/47/7/1227)
- [AAPM routine chest/abdomen/pelvis CT (2014)](https://aapm.org/pubs/CTProtocols/documents/AdultRoutineChestAbdomenPelvisCT.pdf)
- [UCSF: CT patient safety and image quality](https://radiology.ucsf.edu/patient-care/health-professionals/patient-safety-healthcare-professionals/size-and-weight-considerations-imaging-and-image-guided-interventions/info)
- [ESER polytrauma guideline (2020), Tables 9 and 10](https://link.springer.com/article/10.1186/s13244-020-00947-7)

These sources support positioning principles, not universal angle, pixel, or displacement acceptance thresholds for an overhead RGB camera. Diagram widths, proportions, and coordinates are illustrative engineering choices, not clinical thresholds. DICOM's head protocol storage example explicitly demonstrates encoding rather than prescribing clinical practice, so it is not used as a clinical positioning standard here.

## Reference maps

| Preset | Positioning target | Observable relationships | Do not require |
|---|---|---|---|
| `arms_at_sides` | Arms alongside the body for routine head imaging | Each elbow and wrist on its own side; hands near the same-side hip or thigh; arms do not cross the torso | Fully straight arms, fixed palm orientation, fully straight legs, or silhouette matching |
| `arms_overhead` | Both arms overhead for routine chest/abdomen/pelvis imaging | Upper arms directed headward; wrists headward of the shoulders; hands beyond the head; arms clear of the chest/abdomen | Fully straight elbows, touching hands, exact mirror symmetry, or gripping a fixed point |

Both diagrams show the head at the top, matching the bed-head direction. This does not mean every body examination requires head-first entry into the gantry. Actual patient entry direction should be configured independently.

Green indicates illustrative arm target zones; blue indicates landmarks of interest to the camera. The headrest, legs, and silhouette explain the overall position. Green areas are neither scan coverage nor segmentation masks for absolute-coordinate acceptance.

## Integration with top_camera

1. **Select the protocol before detection.** A technologist or upstream examination protocol sets `expected_arm_mode`. The arms-at-sides preset accepts only that arm position; the overhead preset accepts only overhead positioning. Do not infer the required protocol from the observed pose.
2. **Separate bed and body coordinates.** Retain `BedReference` coordinates: u across the bed, v from head to feet. Body coordinates use the shoulder midpoint as origin and the shoulder-to-hip direction as the footward axis, normalized by the patient's shoulder width and torso length. Head, elbows, and wrists lie above the bed plane, so planar projection gives approximate relationships, not precise millimeter locations.
3. **Evaluate relationships rather than outlines.** Use MediaPipe shoulders 11/12, elbows 13/14, wrists 15/16, hips 23/24, knees 25/26, and ankles 27/28. Head estimation may combine nose 0, eyes 2/5, and ears 7/8. The nose does not represent the head vertex; evaluating hands beyond the head requires a head-region estimate. Do not require every hand to stay far from the midline, which could reject valid overhead positions with the hands close together.
4. **Separate the target pose from the movement baseline.** The protocol preset defines the expected pose. After technologist confirmation, save individual reference landmarks for subsequent drift monitoring. Tolerances should account for natural breathing, body proportions, and necessary supports, and must be established using real overhead-camera video. This design does not invent medical angle or displacement thresholds.
5. **States and guidance.** Internally distinguish at least `within_criteria`, `reposition_required`, `not_observable`, and `manual_review_required`; these may still map to Within criteria / Outside criteria in the UI. Ask for arm elevation only when the overhead protocol is selected. If the patient cannot comply, request technologist assistance rather than repeating the instruction.
6. **Observation limits.** An overhead camera provides clues about head rotation and arm position. These diagrams alone cannot confirm supine orientation, chin flexion, bed contact, vertical scanner isocenter, safe gantry clearance, or breath holding. Those require technologist confirmation, device information, or additional sensors. Knee supports should not automatically count as abnormal leg posture.

## Files and reproduction

Files without a language suffix are English. Chinese versions use `_ZH` immediately before the extension.

- `arms_at_sides.svg` / `.png`: editable vector diagram and preview for arms at sides.
- `arms_overhead.svg` / `.png`: editable vector diagram and preview for arms overhead.
- `reference_maps_comparison.png`: side-by-side preview.
- `reference_maps.design.json`: illustration coordinates and preset identifiers only. `clinical_thresholds` is null; this is not detector configuration.
- `render_reference_maps.py`: regenerates English assets using Pillow and the Windows Microsoft YaHei font.
- `render_reference_maps_ZH.py`: regenerates Chinese assets with `_ZH` suffixes, without overwriting the English files.

Run each renderer from any working directory; outputs are written next to the script. Examples from `top_camera/`:

```powershell
.\.venv\Scripts\python.exe reference_maps/render_reference_maps.py
.\.venv\Scripts\python.exe reference_maps/render_reference_maps_ZH.py
```

Future validation should cover both correct poses, a mismatched protocol, one lowered arm, naturally bent elbows, touching hands, body-size variation, knee supports, occlusion, and inability to raise the arms. The implemented presets require the selected arm mode; the body CT preset also checks that both wrists are headward of the estimated head boundary. These engineering rules still need real-camera validation.
