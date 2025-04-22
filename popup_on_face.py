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

# Path to ffmpeg
FFMPEG_PATH = r"C:\Users\AdamStolnits\Downloads\ffmpeg\ffmpeg-20210804-65fdc0e589-win64-static\ffmpeg-20210728-0068b3d0f0-win64-static\bin\ffmpeg.exe"

# Initialize pygame mixer
pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=4096)

# Constants
IMAGE_FOLDER = "images"
VIDEO_FOLDER = "videos"
BACKGROUND_IMAGE = "ver 3 squared forest final.png"

# Load face detection model
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

# Collect and shuffle media
all_image_files = [f for f in os.listdir(IMAGE_FOLDER) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif'))]
all_video_files = [f for f in os.listdir(VIDEO_FOLDER) if f.lower().endswith('.mp4')]
random.shuffle(all_image_files)
random.shuffle(all_video_files)
image_files = all_image_files.copy()
video_files = all_video_files.copy()

# Tkinter setup
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
active_audio = []
last_popup_time = 0
last_detection_time = time.time()

def fade_out_and_destroy(popup):
    try:
        for alpha in range(100, -1, -10):
            if popup.winfo_exists():
                popup.attributes("-alpha", alpha / 100)
                time.sleep(0.03)
        popup.destroy()
        
        # Stop audio when the popup is closed
        pygame.mixer.music.stop()
    except Exception as e:
        print(f"Error stopping audio: {e}")
        pass

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

def show_image_popup(path):
    try:
        img = Image.open(path)
        popup_width = random.randint(200, 400)
        popup_height = random.randint(200, 400)
        img = img.resize((popup_width, popup_height))
        tk_img = ImageTk.PhotoImage(img)
        pos_x = random.randint(0, screen_width - popup_width)
        pos_y = random.randint(0, screen_height - popup_height)
        popup = Toplevel(root)
        popup.geometry(f"{popup_width}x{popup_height}+{pos_x}+{pos_y}")
        popup.overrideredirect(True)
        popup.attributes('-topmost', True)
        lbl = Label(popup, image=tk_img)
        lbl.image = tk_img
        lbl.pack()
        with popup_lock:
            active_popups.append(popup)
    except Exception as e:
        print(f"Error showing image: {e}")

def show_video_popup(path):
    try:
        popup_width = random.randint(200, 400)
        popup_height = random.randint(200, 400)
        pos_x = random.randint(0, screen_width - popup_width)
        pos_y = random.randint(0, screen_height - popup_height)
        popup = Toplevel(root)
        popup.geometry(f"{popup_width}x{popup_height}+{pos_x}+{pos_y}")
        popup.overrideredirect(True)
        popup.attributes('-topmost', True)
        lbl = Label(popup)
        lbl.pack()
        with popup_lock:
            active_popups.append(popup)
        temp_audio_path = extract_audio_to_tempfile(path)
        
        if temp_audio_path:
            try:
                pygame.mixer.music.load(temp_audio_path)
                pygame.mixer.music.play()
            except Exception as e:
                print(f"Error playing audio: {e}")
                os.unlink(temp_audio_path)

        def play_video():
            try:
                video_cap = cv2.VideoCapture(path)
                fps = video_cap.get(cv2.CAP_PROP_FPS)
                delay = int(1000 / fps) if fps > 0 else 30
                while video_cap.isOpened():
                    ret, frame = video_cap.read()
                    if not ret or not popup.winfo_exists():
                        break
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    image = Image.fromarray(frame).resize((popup_width, popup_height))
                    photo = ImageTk.PhotoImage(image)
                    if lbl.winfo_exists():
                        lbl.configure(image=photo)
                        lbl.image = photo
                    cv2.waitKey(delay)
                video_cap.release()

                # Remove the popup from active list after completion
                with popup_lock:
                    if popup in active_popups:
                        active_popups.remove(popup)
                        
                # Call fade out and destroy the popup
                threading.Thread(target=fade_out_and_destroy, args=(popup,), daemon=True).start()

            except Exception as e:
                print(f"Error playing video: {e}")
        threading.Thread(target=play_video, daemon=True).start()
    except Exception as e:
        print(f"Error showing video: {e}")

def show_random_popup():
    global image_files, video_files
    # Check if there are already 5 popups
    with popup_lock:
        if len(active_popups) >= 5:
            # Remove the oldest popup (first one in the queue)
            oldest_popup = active_popups.pop(0)
            # Call fade out and destroy the oldest popup
            threading.Thread(target=fade_out_and_destroy, args=(oldest_popup,), daemon=True).start()
    
    if random.choice(["image", "video"]) == "image" and image_files:
        filename = random.choice(image_files)
        image_files.remove(filename)
        if not image_files:
            image_files = all_image_files.copy()
        show_image_popup(os.path.join(IMAGE_FOLDER, filename))
    elif video_files:
        filename = random.choice(video_files)
        video_files.remove(filename)
        if not video_files:
            video_files = all_video_files.copy()
        show_video_popup(os.path.join(VIDEO_FOLDER, filename))

def close_all_popups():
    with popup_lock:
        for popup in active_popups:
            if popup.winfo_exists():
                threading.Thread(target=fade_out_and_destroy, args=(popup,), daemon=True).start()
        active_popups.clear()
        pygame.mixer.music.stop()

def detection_loop():
    global last_popup_time, last_detection_time
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.1, 5)
        if len(faces) > 0:
            last_detection_time = time.time()
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
