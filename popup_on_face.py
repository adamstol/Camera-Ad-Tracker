import cv2
import os
import random
import threading
import time
from tkinter import Tk, Label, Canvas, Toplevel, NW
from PIL import Image, ImageTk
import pygame
import subprocess
import tempfile
import math

# Path to ffmpeg
FFMPEG_PATH = r"C:\Users\AdamStolnits\Downloads\ffmpeg\ffmpeg-20210804-65fdc0e589-win64-static\ffmpeg-20210728-0068b3d0f0-win64-static\bin\ffmpeg.exe"

# Initialize pygame mixer
pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=4096)

# Constants
IMAGE_FOLDER = "images"
VIDEO_FOLDER = "videos"
BACKGROUND_IMAGE = "ver 3 squared forest final.png"

# Load detection models
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
upper_body_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_upperbody.xml')

# Media files
all_image_files = [f for f in os.listdir(IMAGE_FOLDER) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif'))]
all_video_files = [f for f in os.listdir(VIDEO_FOLDER) if f.lower().endswith('.mp4')]
random.shuffle(all_image_files)
random.shuffle(all_video_files)
image_files = all_image_files.copy()
video_files = all_video_files.copy()

# GUI setup
root = Tk()
screen_width = root.winfo_screenwidth()
screen_height = root.winfo_screenheight()
root.geometry(f"{screen_width}x{screen_height}")
root.attributes('-fullscreen', True)
root.title("Human Detection Display")

bg_img = Image.open(BACKGROUND_IMAGE).resize((screen_width, screen_height))
bg_photo = ImageTk.PhotoImage(bg_img)
canvas = Canvas(root, width=screen_width, height=screen_height)
canvas.pack()
canvas.create_image(0, 0, anchor=NW, image=bg_photo)

cap = cv2.VideoCapture(0)
popup_lock = threading.Lock()
active_popups = []
video_channels = []
last_popup_time = 0
last_detection_time = time.time()
face_center = (screen_width // 2, screen_height // 2)

def fade_out_and_destroy(popup):
    try:
        for alpha in range(100, -1, -10):
            if popup.winfo_exists():
                popup.attributes("-alpha", alpha / 100)
                time.sleep(0.03)
        popup.destroy()
    except Exception as e:
        print(f"Error during fade out: {e}")

def extract_audio_to_tempfile(video_path):
    try:
        temp_audio = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
        temp_audio.close()
        cmd = [
            FFMPEG_PATH,
            '-i', video_path,
            '-vn',
            '-acodec', 'pcm_s16le',
            '-ar', '44100',
            '-ac', '2',
            '-y',
            temp_audio.name
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return temp_audio.name
    except Exception as e:
        print(f"Error extracting audio: {e}")
        return None

def is_area_free(x, y, w, h):
    with popup_lock:
        for popup in active_popups:
            if not popup.winfo_exists():
                continue
            px, py = popup.winfo_x(), popup.winfo_y()
            pw, ph = popup.winfo_width(), popup.winfo_height()
            if not (x + w <= px or px + pw <= x or y + h <= py or py + ph <= y):
                return False
    return True

def get_non_overlapping_position(w, h):
    for _ in range(100):
        x = random.randint(0, screen_width - w)
        y = random.randint(0, screen_height - h)
        if is_area_free(x, y, w, h):
            return x, y
    return random.randint(0, screen_width - w), random.randint(0, screen_height - h)

def move_popup_towards_face(popup):
    try:
        while popup.winfo_exists():
            popup.update_idletasks()
            x, y = popup.winfo_x(), popup.winfo_y()
            w, h = popup.winfo_width(), popup.winfo_height()
            cx, cy = x + w // 2, y + h // 2
            tx, ty = face_center

            dx = (tx - cx) * 0.05
            dy = (ty - cy) * 0.05
            new_x = x + dx
            new_y = y + dy

            with popup_lock:
                for other in active_popups:
                    if other is popup or not other.winfo_exists():
                        continue
                    ox, oy = other.winfo_x(), other.winfo_y()
                    ow, oh = other.winfo_width(), other.winfo_height()

                    # Check for overlap
                    if (new_x < ox + ow and new_x + w > ox and
                        new_y < oy + oh and new_y + h > oy):
                        
                        # Calculate minimal push vector to resolve overlap
                        overlap_x = min(new_x + w - ox, ox + ow - new_x)
                        overlap_y = min(new_y + h - oy, oy + oh - new_y)

                        if overlap_x < overlap_y:
                            if cx < ox + ow / 2:
                                new_x -= overlap_x
                            else:
                                new_x += overlap_x
                        else:
                            if cy < oy + oh / 2:
                                new_y -= overlap_y
                            else:
                                new_y += overlap_y

            final_x = int(max(0, min(screen_width - w, new_x)))
            final_y = int(max(0, min(screen_height - h, new_y)))
            popup.geometry(f"{w}x{h}+{final_x}+{final_y}")
            time.sleep(0.05)
    except Exception as e:
        print(f"Error moving popup: {e}")

def show_image_popup(path):
    try:
        img = Image.open(path)
        w, h = random.randint(150, 300), random.randint(150, 300)
        img = img.resize((w, h))
        tk_img = ImageTk.PhotoImage(img)
        x, y = get_non_overlapping_position(w, h)
        popup = Toplevel(root)
        popup.geometry(f"{w}x{h}+{x}+{y}")
        popup.overrideredirect(True)
        popup.attributes('-topmost', True)
        lbl = Label(popup, image=tk_img)
        lbl.image = tk_img
        lbl.pack()
        with popup_lock:
            active_popups.append(popup)
        threading.Thread(target=move_popup_towards_face, args=(popup,), daemon=True).start()
    except Exception as e:
        print(f"Error showing image: {e}")

def show_video_popup(path):
    try:
        w, h = random.randint(150, 300), random.randint(150, 300)
        x, y = get_non_overlapping_position(w, h)
        popup = Toplevel(root)
        popup.geometry(f"{w}x{h}+{x}+{y}")
        popup.overrideredirect(True)
        popup.attributes('-topmost', True)
        lbl = Label(popup)
        lbl.pack()
        with popup_lock:
            active_popups.append(popup)
        threading.Thread(target=move_popup_towards_face, args=(popup,), daemon=True).start()

        temp_audio_path = extract_audio_to_tempfile(path)
        if temp_audio_path:
            channel = pygame.mixer.find_channel()
            if channel:
                try:
                    sound = pygame.mixer.Sound(temp_audio_path)
                    channel.play(sound)
                    video_channels.append(channel)
                except Exception as e:
                    print(f"Audio error: {e}")
                    os.unlink(temp_audio_path)

        def play_video():
            try:
                cap = cv2.VideoCapture(path)
                fps = cap.get(cv2.CAP_PROP_FPS)
                delay = int(1000 / fps) if fps > 0 else 30
                while cap.isOpened() and popup.winfo_exists():
                    ret, frame = cap.read()
                    if not ret:
                        break
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    img = Image.fromarray(frame).resize((w, h))
                    photo = ImageTk.PhotoImage(img)
                    if lbl.winfo_exists():
                        lbl.configure(image=photo)
                        lbl.image = photo
                    cv2.waitKey(delay)
                cap.release()
                with popup_lock:
                    if popup in active_popups:
                        active_popups.remove(popup)
                threading.Thread(target=fade_out_and_destroy, args=(popup,), daemon=True).start()
            except Exception as e:
                print(f"Video playback error: {e}")

        threading.Thread(target=play_video, daemon=True).start()
    except Exception as e:
        print(f"Error showing video: {e}")

def show_random_popup():
    global image_files, video_files
    with popup_lock:
        if len(active_popups) >= 5:
            oldest = active_popups.pop(0)
            threading.Thread(target=fade_out_and_destroy, args=(oldest,), daemon=True).start()
    if random.choice(["image", "video"]) == "image" and image_files:
        filename = image_files.pop()
        if not image_files:
            image_files = all_image_files.copy()
        show_image_popup(os.path.join(IMAGE_FOLDER, filename))
    elif video_files:
        filename = video_files.pop()
        if not video_files:
            video_files = all_video_files.copy()
        show_video_popup(os.path.join(VIDEO_FOLDER, filename))

def close_all_popups():
    with popup_lock:
        for popup in active_popups:
            if popup.winfo_exists():
                threading.Thread(target=fade_out_and_destroy, args=(popup,), daemon=True).start()
        active_popups.clear()
    for channel in video_channels:
        channel.stop()
    video_channels.clear()

def detection_loop():
    global last_popup_time, last_detection_time, face_center
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.1, 5)
        bodies = upper_body_cascade.detectMultiScale(gray, 1.1, 5)
        detections = faces if len(faces) > 0 else bodies
        if len(detections) > 0:
            last_detection_time = time.time()
            (x, y, w, h) = detections[0]
            raw_x, raw_y = x + w // 2, y + h // 2
            frame_height, frame_width = frame.shape[:2]
            scaled_x = int(raw_x * screen_width / frame_width)
            scaled_y = int(raw_y * screen_height / frame_height)
            face_center = (screen_width - scaled_x, scaled_y)
            if time.time() - last_popup_time > random.uniform(2, 4):
                last_popup_time = time.time()
                threading.Thread(target=show_random_popup, daemon=True).start()
        elif time.time() - last_detection_time > 1:
            close_all_popups()
        cv2.waitKey(100)

threading.Thread(target=detection_loop, daemon=True).start()
root.mainloop()
cap.release()
pygame.mixer.quit()
