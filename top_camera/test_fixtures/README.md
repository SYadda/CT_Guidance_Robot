# Bed calibration regression fixture

`daylight_calibration.jpg` contains only the camera-photo portion of the user-supplied daylight calibration screenshot (2026-10-24). The old, incorrect yellow floor-mat outline is preserved in that screenshot; it is not a target annotation produced by the updated detector.

The regression target is the central white table, approximately x=0.14..0.79 and y=0.35..0.69 in this fixture. These coordinates are test assertions only; production detection does not use fixed scene coordinates. Tests also vary exposure, add smooth shading, and rotate the frame slightly. They do not establish accuracy for other rooms or arbitrary lighting.
