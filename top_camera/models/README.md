# Pose model

`pose_landmarker_full.task` is Google's MediaPipe Full Pose Landmarker model,
downloaded from the official MediaPipe model repository. It predicts body
landmarks and a person segmentation mask locally. No personal photograph is
used to train it in this project.

Source: https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/1/pose_landmarker_full.task

Documentation: https://developers.google.com/edge/mediapipe/solutions/vision/pose_landmarker/python

The Full Pose task model is Apache-2.0, as confirmed by the MediaPipe maintainer:
https://github.com/google-ai-edge/mediapipe/issues/6306

MediaPipe's prebuilt Python runtime may attempt usage-metrics connections;
image inference does not require a network connection. No application code
uploads the captured photographs. Offline operation is supported by the model.
