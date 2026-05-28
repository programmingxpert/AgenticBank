import urllib.request
import zipfile
import os

MODEL_URL = "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip"
MODEL_DIR = "model"

def main():
    if not os.path.exists(MODEL_DIR):
        print("Downloading Vosk model...")
        urllib.request.urlretrieve(MODEL_URL, "model.zip")
        print("Extracting model...")
        with zipfile.ZipFile("model.zip", 'r') as zip_ref:
            zip_ref.extractall(".")
        os.rename("vosk-model-small-en-us-0.15", MODEL_DIR)
        os.remove("model.zip")
        print("Vosk model downloaded successfully!")
    else:
        print("Vosk model already exists.")

if __name__ == "__main__":
    main()
