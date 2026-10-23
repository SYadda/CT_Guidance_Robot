# Patient & Room Readiness

[中文说明](readme_ZH.md) · [技术流程（中文）](TECHNICAL_FLOW_ZH.md)

A local demonstration that uses one fixed USB camera to check a patient's position and visible changes around a CT-style bed. The only final results are **ready** and **not ready**. Patient position, short-term stillness, and the visible scene must all pass. Uncertain patient detection returns **not ready**.

## Repository layout

The fixed-camera application is contained in `top_camera/`. `LICENSE` and the repository-wide `.gitignore` stay at the repository root alongside other independently maintained modules. All application paths in this README are relative to `top_camera/`.

From the repository root, enter the application directory before running commands:

```powershell
cd top_camera
```

## Requirements and startup

- Windows with Python 3.12 and a USB camera.
- Edge or Chrome on the computer connected to the camera; allow camera access.
- The local `models/pose_landmarker_full.task` model and Python dependencies.

On this computer, the environment and model are already installed. Double-click `start_demo.bat`, then open [http://localhost:8000](http://localhost:8000).

For a new computer, run from the project directory:

```powershell
powershell -ExecutionPolicy Bypass -File .\setup_demo.ps1
.\.venv\Scripts\python.exe app.py
```

Setup downloads the dependencies and the official Google Full Pose Landmarker model. See [model information](models/README.md). Image inference runs locally and does not require an internet connection. The application does not upload photographs; the prebuilt MediaPipe runtime may attempt usage-metrics connections.

The server binds only to `127.0.0.1`. Optional arguments:

```powershell
.\.venv\Scripts\python.exe app.py --port 8001 --storage runtime/test_session
```

## Demonstration workflow

1. Fix the camera in position. Clear the bed and surrounding scene, leaving the expected equipment in place.
2. Click **Calibrate**. The application captures five frames and creates an empty-scene baseline.
3. Review the automatically detected **yellow bed outline**. Corners 1–2 identify the head end. Use **Swap head / foot** if needed. If detection is inaccurate, use **Correct bed outline** and click the four corners around the bed, starting at a head-end corner. The program identifies the long and short edges automatically.
4. Select **Yellow outline and head end are correct**. Confirm the room is empty and prepared, then click **Use as baseline**. Optional **Ignore area** regions can cover small moving cables; objects in ignored regions will also be missed. Do not mask the bed.
5. Ask the participant to lie on their back along the bed, with both arms beside the torso or both arms overhead, legs in the expected relaxed position, and remain still. Click **Check**.
6. The application captures three frames over approximately half a second and checks position, movement, and the visible background. **Blue boxes** identify position/visibility issues; **red boxes** identify scene differences.
7. Correct the issue and click **Check again**.

The calibration preview expires after five minutes. Restarting the service requires a new calibration; disk snapshots are not automatically restored as an active baseline. Recalibrate after moving the camera or bed or changing the camera/resolution. An empty bed returns **not ready**, because this workflow requires a patient to be present.

## How checks work

- MediaPipe estimates 33 body landmarks and a person mask. Rules use bed coordinates, joint angles, and distances relative to the participant's own shoulder width and torso length; no silhouette matching or personal training is used.
- The demo allows modest rotation and natural limb placement. Approximately 28 degrees of body-axis rotation is tolerated, provided the other position rules still pass.
- A short detection dropout or small landmark jitter is tolerated. At least two of three frames must pass, including the last frame; clear movement still blocks readiness.
- Patient pixels, nearby margins, and narrow foot regions are excluded from empty-scene differencing. The entire bed and the patient's bounding rectangle are not excluded.
- Background checks compensate exposure and smooth lighting changes, suppress likely shadows/reflections, and support small camera roll (up to about 2.5 degrees) and small translations when registration is reliable.

## Project layout

| Path | Purpose |
|---|---|
| `app.py` | Local HTTP service, calibration session, combined decision and saved results |
| `bed_detection.py` | Automatic empty-bed outline proposal |
| `positioning.py` | Pose model, bed coordinates, posture rules and patient exclusion mask |
| `calibration.py` | Empty-scene baseline, alignment, lighting compensation and difference boxes |
| `web/` | Browser UI, USB camera capture and overlays |
| `models/` | Local pose model and source information |
| `test_demo.py`, `test_positioning.py` | API and algorithm regression tests |
| `runtime/` | Generated calibration snapshots and check records |
| `archive/` | Historical code, reference documents, sample photographs and development outputs |

`.venv/` is the installed local Python environment. Keep it for the current computer; use the setup script on another machine.

## Local API

All image inputs are JPEG data URLs. `camera` contains `device_id`, `width`, and `height` from the video device. Bed corners and box coordinates are normalized to `[0, 1]`.

| Method and path | Purpose |
|---|---|
| `GET /api/state` | Calibration ID, state and confirmed bed corners |
| `POST /api/calibration/capture` | Five `images` and `camera`; returns a preview, `candidate_id` and proposed `bed_corners` (or null) |
| `POST /api/calibration/confirm` | `candidate_id`, `empty_room_confirmed: true`, `bed_confirmed: true`, `bed_corners`, and `ignored_regions` |
| `POST /api/check` | Three `images`, `camera`, and `calibration_id`; returns final and component results with red/blue boxes |

The check response includes `ready`, `status`, `scene_ready`, `pose_ready`, `anomaly_boxes`, and `pose_boxes`. A single image can be submitted for diagnosis, but cannot produce final readiness without stillness evidence. Invalid requests or stale calibration return HTTP errors such as 400/409, rather than a valid check result.

`runtime/baseline.jpg` and `baseline.json` are snapshots only. Check photographs and JSON results are retained in `runtime/checks/`, approximately up to 200 checks or 250 MiB, with the oldest files removed when limits are exceeded.

## Verification

```powershell
.\.venv\Scripts\python.exe -m unittest -v test_demo.py test_positioning.py
```

Tests cover calibration and confirmation gates, relative posture rules, short-term movement, lighting/rotation tolerance, patient masking, visible objects, and the combined readiness decision. These are development checks, not a clinical accuracy study.

## Limitations

This is a fixed-camera demonstration, not a clinical CT scan authorization system; it does not control a CT scanner, ACU, or robot. Actual positioning follows the radiographer's examination protocol.

A single RGB view cannot reliably establish all 3D postures, exact supine/prone orientation, body contact with the bed, or breath holding. Keep the full patient and both hands visible. Body shape, glare, darkness, and occlusion can still cause errors.

Scene differences do not identify object classes. Objects hidden by the patient or included in the person/foot mask cannot be checked. Relaxed lighting tolerance reduces sensitivity to small, gray/black, low-contrast objects. Three frames establish only brief stability, not continuous monitoring.

## Archive

See [archive index](archive/README.md). Archived material is not imported or served by the current application. Development photo-review scripts retain their historical path assumptions and are not current entry points.
