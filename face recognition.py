import os, cv2, time, mediapipe
from deepface import DeepFace



show_ui = True
average_face_width_meters = 0.15
# Geschätzte Brennweite der Kamera in Pixeln
camera_focal_length = 2000
close_distance_threshold_meters = 1
# blaze_face_full_range.tflite is better and more expensive than blaze_face_full_range_sparse.tflite
model_file_path = "blaze_face_full_range.tflite" 
face_images_folder = "faces"



BaseOptions = mediapipe.tasks.BaseOptions
FaceDetector = mediapipe.tasks.vision.FaceDetector
FaceDetectorOptions = mediapipe.tasks.vision.FaceDetectorOptions
VisionRunningMode = mediapipe.tasks.vision.RunningMode

latest_result = None

def update_result(result, output_image: mediapipe.Image, timestamp_ms: int):
    global latest_result
    latest_result = result

os.chdir(os.path.dirname(os.path.abspath(__file__)))

DeepFace.build_model("ArcFace")

faces = {}
for file in os.listdir(face_images_folder):
    name = os.path.splitext(file)[0]
    img = cv2.imread(os.path.join(face_images_folder, file))
    if img is not None:
        faces[name] = img

cap = cv2.VideoCapture(0)

with FaceDetector.create_from_options(
    FaceDetectorOptions(
        base_options=BaseOptions(model_asset_path=model_file_path),
        running_mode=VisionRunningMode.LIVE_STREAM,
        result_callback=update_result)
    ) as detector:

    while cap.isOpened():

        success, frame = cap.read()
        if not success:
            break
        
        mp_image = mediapipe.Image(image_format=mediapipe.ImageFormat.SRGB, data=cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        
        detector.detect_async(mp_image, int(time.time() * 1000))
        
        if latest_result and latest_result.detections:

            for detection in latest_result.detections:



                bbox = detection.bounding_box
                x, y, w, h = bbox.origin_x, bbox.origin_y, bbox.width, bbox.height

                distance = camera_focal_length * average_face_width_meters / w
                face_close_enough = distance <= close_distance_threshold_meters

                if face_close_enough:
                    
                    crop_y1, crop_y2 = max(0, y), min(frame.shape[0], y + h)
                    crop_x1, crop_x2 = max(0, x), min(frame.shape[1], x + w)
                    face_crop = frame[crop_y1:crop_y2, crop_x1:crop_x2]

                    if face_crop.size > 0:

                        text_to_show = "unknown face"

                        for name, face in faces.items():

                            try:
                                verification = DeepFace.verify(img1_path=face_crop, img2_path=face, model_name="ArcFace",
                                                                enforce_detection=False, silent=True)
                                if verification["verified"]:
                                    text_to_show = name
                                    break
                            except ValueError:
                                pass

                else:
                    text_to_show = "too far away"

                text_to_show += f"\n{distance:.2f}m"

                if show_ui:
                    color = ((0, 255, 0) if text_to_show != "unknown face" else (0, 0, 255)) if face_close_enough else (255, 0, 0)
                    cv2.rectangle(frame, (x, y), (x + w, y + h), color, 5)
                    cv2.putText(frame, text_to_show, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 3, color, 2)



        if show_ui:
            cv2.imshow("where face detection", frame)
            if cv2.waitKey(1) & 0xFF == 27:
                break

cap.release()
cv2.destroyAllWindows()