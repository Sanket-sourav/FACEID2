from deepface import DeepFace
import cv2
import os
import sys

# Define our directories
raw_dir = "raw_student_photos/"
clean_dir = "student_photos/"

def preprocess_faces():
    print("Starting preprocessing and alignment...")

    # Check that there are raw photos to process
    if not os.path.exists(raw_dir):
        print(f"ERROR: Raw photos directory '{raw_dir}' does not exist. Add photos and retry.")
        sys.exit(1)

    raw_images = [f for f in os.listdir(raw_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
    if not raw_images:
        print(f"ERROR: No image files found in '{raw_dir}'. Add raw student photos and retry.")
        sys.exit(1)

    # Create the clean directory if it doesn't exist
    if not os.path.exists(clean_dir):
        os.makedirs(clean_dir)

    # Loop through every photo in the raw directory
    for filename in raw_images:
        raw_path = os.path.join(raw_dir, filename)
        clean_path = os.path.join(clean_dir, filename)

        try:
            # Extract and align the face using RetinaFace
            face_objs = DeepFace.extract_faces(
                img_path=raw_path,
                detector_backend="retinaface",
                align=True,
                enforce_detection=True
            )

            if face_objs:
                # Grab the first face found in the image
                face_array = face_objs[0]['face']

                # DeepFace returns the image in RGB (0 to 1 scale)
                # OpenCV expects BGR (0 to 255 scale) for saving, so we convert it
                face_array = face_array[:, :, ::-1] * 255

                # Save the cleaned, cropped, and aligned face
                cv2.imwrite(clean_path, face_array)
                print(f"Successfully aligned and saved: {filename}")

        except Exception as e:
            print(f"Skipping {filename} - No clear face detected or error: {e}")


if __name__ == "__main__":
    preprocess_faces()
    print("\nPreprocessing complete. You can now inspect the 'student_photos' folder.")