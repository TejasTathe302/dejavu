import os
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
from tkinter import ttk
import json
import sys
from os.path import isdir, join
import time
import wave
import pyaudio

from dejavu import Dejavu
from dejavu.logic.recognizer.file_recognizer import FileRecognizer
from dejavu.logic.recognizer.microphone_recognizer import MicrophoneRecognizer

DEFAULT_CONFIG_FILE = "dejavu.cnf.SAMPLE"
RECORD_DIR = "recorded/"  # Directory to store recorded files

if not os.path.exists(RECORD_DIR):
    os.makedirs(RECORD_DIR)


def init(configpath):
    """
    Load config from a JSON file
    """
    try:
        with open(configpath) as f:
            config = json.load(f)
    except IOError as err:
        messagebox.showerror("Error", f"Cannot open configuration: {str(err)}. Exiting")
        sys.exit(1)

    # create a Dejavu instance
    return Dejavu(config)


class DejavuApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Dejavu - Audio Fingerprinting")
        self.root.geometry("800x800")  # Set page size to 800x800

        self.config_file = DEFAULT_CONFIG_FILE
        self.djv = init(self.config_file)

        self.create_widgets()

    def print_all_songs(self):
        """Retrieve and print all songs from the songs table."""
        songs = self.djv.db.get_songs()
        if songs:
            print("All Songs in Database:")
            print(songs)
            songs = list(songs)
            for song in songs:
                print(f"ID: {song['song_id']}, Name: {song['song_name']}, "
                    f"Total Hashes: {song['total_hashes']}, "
                    f"Created: {song['date_created']}")
            messagebox.showinfo("Info", "Songs printed to console successfully.")
        else:
            messagebox.showinfo("Info", "No songs found in the database.")


    def create_widgets(self):
        # Existing buttons
        self.fingerprint_button = tk.Button(self.root, text="Fingerprint Directory", command=self.fingerprint_directory)
        self.fingerprint_button.pack(pady=10)

        self.record_store_button = tk.Button(self.root, text="Record and Store from Microphone", command=self.record_and_store)
        self.record_store_button.pack(pady=10)

        self.recognize_file_button = tk.Button(self.root, text="Recognize from File", command=self.recognize_file)
        self.recognize_file_button.pack(pady=10)

        self.recognize_mic_button = tk.Button(self.root, text="Recognize from Microphone", command=self.recognize_mic)
        self.recognize_mic_button.pack(pady=10)

        # New button to print all songs
        self.print_songs_button = tk.Button(self.root, text="Print All Songs", command=self.print_all_songs)
        self.print_songs_button.pack(pady=10)

        # Status Label
        self.status_label = tk.Label(self.root, text="", font=("Helvetica", 12))
        self.status_label.pack(pady=10)

        # Results Table (existing code unchanged)
        columns = ("Song ID", "Song Name", "Total Hashes", "Hashes in DB", "Hashes Matched", "Input Confidence", "Fingerprinted Confidence", "Offset", "Offset Seconds", "Matched/Total (%)", "Matched/DB (%)")
        self.results_tree = ttk.Treeview(self.root, columns=columns, show="headings")

        for col in columns:
            self.results_tree.heading(col, text=col)
            self.results_tree.column(col, width=120)

        self.results_tree.pack(pady=10, fill="both", expand=True)

    def fingerprint_directory(self):
        directory = filedialog.askdirectory(title="Select Directory to Fingerprint")
        if not directory:
            messagebox.showwarning("Warning", "No directory selected.")
            return

        extension = simpledialog.askstring("Input", "Enter file extension to fingerprint (e.g., mp3, wav):")
        if not extension:
            messagebox.showwarning("Warning", "No extension provided.")
            return

        self.status_label.config(text="Uploading... Please wait.")
        self.root.update()

        self.djv.fingerprint_directory(directory, ["." + extension], 4)

        self.status_label.config(text="Fingerprinting completed.")
        messagebox.showinfo("Info", "Fingerprinting completed.")

    def recognize_file(self):
        file_path = filedialog.askopenfilename(title="Select Audio File to Recognize")
        if not file_path:
            messagebox.showwarning("Warning", "No file selected.")
            return

        self.status_label.config(text="Recognizing... Please wait.")
        self.root.update()

        try:
            songs = self.djv.recognize(FileRecognizer, file_path)
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred during recognition: {str(e)}")
            return

        self.status_label.config(text="Recognition completed.")
        self.display_results(songs['results'])

    def recognize_mic(self):
        seconds = simpledialog.askinteger("Input", "Enter number of seconds to record from microphone:")
        if not seconds:
            messagebox.showwarning("Warning", "No duration provided.")
            return

        self.status_label.config(text="Recording...")
        self.root.update()

        songs = self.djv.recognize(MicrophoneRecognizer, seconds=seconds)

        self.status_label.config(text="Recognition completed.")
        self.display_results(songs[0])

    def record_and_store(self):
        """Record audio from the microphone and store it in the 'recorded/' directory"""
        dialog = DurationAndFileNameDialog(self.root)
        seconds = dialog.duration
        file_name = dialog.file_name
        print("seconds",seconds)
        print("file_name",file_name)
        if not seconds:
            messagebox.showwarning("Warning", "No duration provided.")
            return

        if not file_name:
            messagebox.showwarning("Warning", "No file name provided.")
            return

        file_name = f"{file_name}.wav"  # Add the .wav extension
        file_path = f"recorded/{file_name}"

        self.status_label.config(text="Recording...")
        self.root.update()

        file_path = self.record_audio(seconds, file_path)
        if file_path:
            self.status_label.config(text="Fingerprinting the recorded file... Please wait.")
            self.root.update()
            try:
                self.djv.fingerprint_file(file_path, file_name)
                self.status_label.config(text="Fingerprinting completed.")
                messagebox.showinfo("Success", f"File '{file_name}' recorded and fingerprinted successfully!")
            except Exception as e:
                messagebox.showerror("Error", f"An error occurred while fingerprinting: {str(e)}")
                self.status_label.config(text="Error in fingerprinting.")
    def record_audio(self, seconds,file_path):
        """Record audio for a given number of seconds and save it to a file."""
        format = pyaudio.paInt16  # 16-bit resolution
        channels = 1  # 1 channel
        rate = 44100  # 44.1kHz sampling rate
        chunk = 1024  # 2^10 samples for buffer
        audio = pyaudio.PyAudio()  # create pyaudio instantiation

        stream = audio.open(format=format, rate=rate, channels=channels,
                            input=True, frames_per_buffer=chunk)

        frames = []
        for i in range(0, int(rate / chunk * seconds)):
            data = stream.read(chunk)
            frames.append(data)

        stream.stop_stream()
        stream.close()
        audio.terminate()


        # Save the recorded data as a WAV file
        wavefile = wave.open(file_path, 'wb')
        wavefile.setnchannels(channels)
        wavefile.setsampwidth(audio.get_sample_size(format))
        wavefile.setframerate(rate)
        wavefile.writeframes(b''.join(frames))
        wavefile.close()

        return file_path

    def calculate_ratios(self, song):
        total_hashes = song.get("input_total_hashes", 0)
        hashes_in_db = song.get("fingerprinted_hashes_in_db", 0)
        hashes_matched = song.get("hashes_matched_in_input", 0)

        matched_to_total_ratio = (hashes_matched / total_hashes) * 100 if total_hashes > 0 else 0
        matched_to_db_ratio = (hashes_matched / hashes_in_db) * 100 if hashes_in_db > 0 else 0

        return matched_to_total_ratio, matched_to_db_ratio

    def display_results(self, songs):
        # Clear previous results
        for item in self.results_tree.get_children():
            self.results_tree.delete(item)

        columns = ("Song ID", "Song Name", "Total Hashes", "Hashes in DB", "Hashes Matched", "Input Confidence", "Fingerprinted Confidence", "Offset", "Offset Seconds", "Matched/Total (%)", "Matched/DB (%)")

        # Update the treeview columns
        self.results_tree["columns"] = columns
        for col in columns:
            self.results_tree.heading(col, text=col)
            self.results_tree.column(col, width=120)

        if isinstance(songs, list) and songs:
            for song in songs:
                if isinstance(song, dict):
                    matched_to_total_ratio, matched_to_db_ratio = self.calculate_ratios(song)
                    self.results_tree.insert("", "end", values=(
                        song.get("song_id", "Unknown"),
                        song.get("song_name", "Unknown").decode("utf-8") if isinstance(song.get("song_name"), bytes) else song.get("song_name", "Unknown"),
                        song.get("input_total_hashes", "Unknown"),
                        song.get("fingerprinted_hashes_in_db", "Unknown"),
                        song.get("hashes_matched_in_input", "Unknown"),
                        song.get("input_confidence", "Unknown"),
                        song.get("fingerprinted_confidence", "Unknown"),
                        song.get("offset", "Unknown"),
                        song.get("offset_seconds", "Unknown"),
                        f"{matched_to_total_ratio:.2f}%",
                        f"{matched_to_db_ratio:.2f}%"
                    ))
                else:
                    self.results_tree.insert("", "end", values=("Unknown",) * len(columns))
        else:
            self.results_tree.insert("", "end", values=("No match found",) + ("",) * (len(columns) - 1))



class DurationAndFileNameDialog(simpledialog.Dialog):
    def body(self, master):
        tk.Label(master, text="Enter a name for the recorded file:").grid(row=0)
        tk.Label(master, text="Enter number of seconds to record:").grid(row=1)

        self.file_name_entry = tk.Entry(master)
        self.duration_entry = tk.Entry(master)

        self.file_name_entry.grid(row=0, column=1)
        self.duration_entry.grid(row=1, column=1)

        return self.file_name_entry  # initial focus

    def apply(self):
        try:
            self.duration = int(self.duration_entry.get())
        except ValueError:
            self.duration = None
        self.file_name = self.file_name_entry.get()


if __name__ == "__main__":
    root = tk.Tk()
    app = DejavuApp(root)
    root.mainloop()
