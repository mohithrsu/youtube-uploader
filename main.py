import os, time, json, pickle, base64
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
VIDEOS_DIR = "videos"
UPLOADED_DIR = "uploaded"
SLEEP_SECONDS = 5820  # 1 hour 37 minutes

def write_env_files():
    if "CLIENT_SECRET_JSON" in os.environ and not os.path.exists("client_secret.json"):
        with open("client_secret.json", "w", encoding="utf-8") as f:
            f.write(os.environ["CLIENT_SECRET_JSON"])
    if "TOKEN_PICKLE" in os.environ and not os.path.exists("token.pickle"):
        data = os.environ["TOKEN_PICKLE"]
        try:
            b = base64.b64decode(data)
            with open("token.pickle", "wb") as f:
                f.write(b)
        except Exception:
            with open("token.pickle", "wb") as f:
                f.write(data.encode())

def ensure_dirs():
    os.makedirs(VIDEOS_DIR, exist_ok=True)
    os.makedirs(UPLOADED_DIR, exist_ok=True)

def get_credentials():
    write_env_files()
    creds = None
    if os.path.exists("token.pickle"):
        with open("token.pickle", "rb") as f:
            creds = pickle.load(f)
    if creds and creds.valid:
        return creds
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open("token.pickle", "wb") as f:
            pickle.dump(creds, f)
        return creds
    if not os.path.exists("client_secret.json"):
        raise FileNotFoundError("client_secret.json missing. Set CLIENT_SECRET_JSON env or upload the file locally.")
    flow = InstalledAppFlow.from_client_secrets_file("client_secret.json", SCOPES)
    creds = flow.run_local_server(port=0)
    with open("token.pickle", "wb") as f:
        pickle.dump(creds, f)
    return creds

def build_youtube_service(creds):
    return build("youtube", "v3", credentials=creds)

def upload_one(youtube, filepath):
    filename = os.path.basename(filepath)
    body = {
        "snippet": {"title": filename, "description": "", "tags": []},
        "status": {"privacyStatus": "public"}
    }
    media = MediaFileUpload(filepath, chunksize=-1, resumable=True)
    req = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    resp = None
    while resp is None:
        status, resp = req.next_chunk()
        if status:
            print(f"Uploading {filename}: {int(status.progress() * 100)}%")
    print(f"Uploaded {filename} -> {resp.get('id')}")
    return resp

def worker_loop():
    ensure_dirs()
    creds = get_credentials()
    youtube = build_youtube_service(creds)
    while True:
        files = sorted([f for f in os.listdir(VIDEOS_DIR) if f.lower().endswith(".mp4")])
        if files:
            pick = files[0]
            path = os.path.join(VIDEOS_DIR, pick)
            try:
                upload_one(youtube, path)
                os.replace(path, os.path.join(UPLOADED_DIR, pick))
            except Exception as e:
                print("Upload failed:", e)
        else:
            print("No videos in folder. Waiting...")
        time.sleep(SLEEP_SECONDS)

# Render worker compatible entry point
worker_loop()

