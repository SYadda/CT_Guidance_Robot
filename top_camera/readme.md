# Patient-only CT Position Monitoring

[Chinese documentation](readme_ZH.md)

The current `top_camera/` application checks the patient on the bed only. The previous patient-and-scene version is preserved in `../archive/top_camera/`. Background clutter, room changes, scene differences and person segmentation are not part of this version's decision.

## Start

Double-click `start_demo.bat`, then open [http://localhost:8001](http://localhost:8001). The launcher uses this directory's `.venv/` Python environment. The model and application files are local to this directory; monitoring records are written to its own `runtime/`.

On another computer, run `setup_demo.ps1` to create a local environment and install dependencies. Default port: 8001 (the original version defaults to 8000).

## Workflow

1. Click **Calibrate** to capture a bed preview. An unobstructed bed helps automatic outline detection; otherwise mark its four corners manually. Light and dark mattresses and moderately shorter bed outlines are supported. If detection fails, no fabricated bed outline is used. No empty-room baseline or background stability check is performed.
2. Confirm the yellow outline and head end, then click **Use bed outline**.
3. Choose **Head CT** for arms at the sides or **Chest / Abdomen / Pelvis CT** for both arms overhead.
4. The camera remains open and submits one new frame per second when processing permits. The first three frames establish short-term stability.
5. Before the first analyzed photo returns, only a neutral startup message is shown. After a result arrives, the page displays green **Within criteria** or red **Outside criteria**, blue posture boxes, and simple English repositioning instructions. The yellow bed outline is shown only during bed calibration and review; patient monitoring shows blue posture boxes only. Select the other CT button to switch protocols, or **Stop monitoring** to stop.

Hands resting inside the shoulder-to-hip torso region are rejected, including hands on the chest or abdomen. Visible finger landmarks near each wrist supplement wrist positions. This is a 2D landmark check and still depends on detection accuracy.

The decision includes patient visibility, position relative to the bed, arm position required by the selected protocol, legs, lying-flat cues and short-term movement. Background changes cannot independently cause an Outside criteria result. If clutter obscures the patient, the resulting visibility or landmark errors may still prevent a pass.

People whose detected hip center lies outside the bed region are excluded from patient selection. The region includes small margins for projection uncertainty. A second distinct, confident person inside that region still blocks the check. This is a geometric filter, not patient identity recognition.

Calibration must be repeated after a server restart, camera/resolution change, or movement of the bed/camera. Hidden pages pause monitoring. Results expire after three seconds; slow processing does not build a request queue.

## API and validation

The API retains `/api/state`, `/api/calibration/capture`, `/api/calibration/confirm` and `/api/check`. Confirmation requires `candidate_id`, `bed_confirmed: true` and `bed_corners`; it does not require an empty-room confirmation or ignored regions. Monitoring checks require `camera`, `calibration_id`, `exam_type` (`head_ct` / `body_ct`), `monitor_id` and one new JPEG image in `images`.

Results contain `ready` (Boolean), `status`, `pose_ready`, `pose_boxes`, `guidance`, `scene_checked: false`, and protocol/timing metadata. There is no scene readiness decision or red anomaly-box output.

From this directory, run:

```powershell
.\.venv\Scripts\python.exe -m unittest -v test_patient_only.py
```

Tests use synthetic landmarks and simulated detections; they do not establish real-camera or clinical accuracy. A single RGB camera cannot confirm all 3D posture, bed contact, or supine/prone orientation. This version does not control scan start or notify an ACU.

## Daylight bed detection

Calibration combines contour proposals with paired long bed rails. Candidate scoring favors a coherent bright table over a dark floor mat, and rail/end refinement uses signed edges to avoid following daylight reflections or a nearby cabinet. Dark-mattress contour fallback remains available. No camera-specific bed coordinates are hard-coded. The supplied daylight screenshot is included as a regression fixture with exposure, smooth-shadow and small-rotation variants; this does not guarantee detection in every room. Confirm the proposed outline and head end as before.
