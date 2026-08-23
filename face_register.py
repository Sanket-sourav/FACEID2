import os
import sys
import pickle
from deepface import DeepFace

# Path to the folder containing individual 1-3 clear photos of each student
db_path = "student_photos/"
representations_file = os.path.join(db_path, "representations_arcface.pkl")

def ensure_db_ready():
    if not os.path.exists(db_path):
        raise RuntimeError(f"Database folder '{db_path}' does not exist. Run 'preprocess.py' first.")

    images = [f for f in os.listdir(db_path) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
    if not images:
        raise RuntimeError(f"No images found in '{db_path}'. Run 'preprocess.py' first to populate it.")

    if os.path.exists(representations_file):
        print("Embeddings already present:", representations_file)
        return

    # Build representations explicitly by computing embeddings for each image
    print(f"Building face embedding database for {len(images)} image(s) in '{db_path}' ...")
    representations = []
    errors = []

    for fname in images:
        img_path = os.path.join(db_path, fname)
        try:
            emb = DeepFace.represent(img_path=img_path, model_name="ArcFace", detector_backend="retinaface", enforce_detection=False)
            # Ensure embedding is a plain list for pickle compatibility
            if hasattr(emb, 'tolist'):
                emb_list = emb.tolist()
            else:
                emb_list = list(emb)

            representations.append({
                'identity': img_path,
                'embedding': emb_list
            })
            print("Embedded:", fname)
        except Exception as e:
            errors.append((fname, str(e)))
            print(f"Failed to embed {fname}: {e}")

    # Write representations to file
    try:
        with open(representations_file, 'wb') as f:
            pickle.dump(representations, f)

        if os.path.exists(representations_file):
            print("Database built successfully! Embeddings stored at", representations_file)
        else:
            print("ERROR: representations file was not created despite no exception. Check filesystem permissions.")
    except Exception as e:
        raise RuntimeError(f"Error writing representations file: {e}")

    if errors:
        print("Some images failed to embed:")
        for fname, msg in errors:
            print(" -", fname, ":", msg)


if __name__ == "__main__":
    try:
        ensure_db_ready()
    except RuntimeError as e:
        print("ERROR:", e)
        sys.exit(1)