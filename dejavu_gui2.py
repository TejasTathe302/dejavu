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

    def show_all_songs(self):
        """Display all songs in the database with a delete option."""
        # Create a new window for displaying songs
        songs_window = tk.Toplevel(self.root)
        songs_window.title("All Songs")
        songs_window.geometry("900x400")  # Set the window size

        # Create Treeview widget
        columns = ("song_id", "song_name", "file_sha1", "total_hashes", "date_created", "delete")
        tree = ttk.Treeview(songs_window, columns=columns, show="headings")
        tree.pack(fill="both", expand=True)

        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=100 if col == "delete" else 150)

        # Retrieve songs from the database
        songs = self.djv.db.get_songs()

        # Add songs to the Treeview
        for song in songs:
            tree.insert("", "end", values=(
                song["song_id"],
                song["song_name"],
                song["file_sha1"],
                song["total_hashes"],
                song["date_created"],
                "Delete"
            ))

        # Add the Delete button functionality
        def on_delete(event):
            item = tree.selection()[0]  # Get the selected item
            song_id = tree.item(item, "values")[0]  # Get the song_id of the selected item
            self.delete_song(song_id)  # Delete the song from the database
            tree.delete(item)  # Remove the item from the Treeview

        tree.bind("<Double-1>", on_delete)  # Bind double-click to delete function

        # Add an instruction label
        label = tk.Label(songs_window, text="Double-click 'Delete' to remove a song.", font=("Helvetica", 12))
        label.pack(pady=10)

    def delete_song(self, song_id):
        """Delete a song from the database by song_id."""
        try:
            query = "DELETE FROM songs WHERE song_id = ?"
            self.djv.db.cursor.execute(query, (song_id,))
            self.djv.db.conn.commit()
            messagebox.showinfo("Info", f"Song with ID {song_id} deleted successfully.")
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred while deleting the song: {str(e)}")

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

        # New button to show all songs with delete option
        self.show_songs_button = tk.Button(self.root, text="Show All Songs", command=self.show_all_songs)
        self.show_songs_button.pack(pady=10)

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
        # seconds = simpledialog.askinteger("Input", "Enter number of seconds to record from microphone:")
        seconds=5
        if not seconds:
            messagebox.showwarning("Warning", "No duration provided.")
            return

        self.status_label.config(text="Recording till 5 sec...")
        self.root.update()

        songs = self.djv.recognize(MicrophoneRecognizer, seconds=seconds)

        self.status_label.config(text="Recognition completed.")
        self.display_results(songs[0])

    def record_and_store(self):
        """Record audio from the microphone and store it in the 'recorded/' directory"""
        dialog = DurationAndFileNameDialog(self.root)
        seconds = dialog.duration
        file_name = dialog.file_name
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
        format = pyaudio.paInt16
        channels = 1
        rate = 44100
        chunk = 1024

        audio = pyaudio.PyAudio()

        stream = audio.open(format=format, channels=channels,
                            rate=rate, input=True,
                            frames_per_buffer=chunk)

        frames = []

        for i in range(0, int(rate / chunk * seconds)):
            data = stream.read(chunk)
            frames.append(data)

        stream.stop_stream()
        stream.close()
        audio.terminate()

        with wave.open(file_path, 'wb') as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(audio.get_sample_size(format))
            wf.setframerate(rate)
            wf.writeframes(b''.join(frames))

        return file_path

    def display_results(self, results):
        """Display recognition results in the Treeview."""
        if not results:
            messagebox.showinfo("No Match", "No matching song found.")
            return

        self.results_tree.delete(*self.results_tree.get_children())

        for result in results:
            song_id = result['song_id']
            song_name = result['song_name']
            total_hashes = result['input_total_hashes']
            hashes_in_db = result['fingerprinted_hashes_in_db']
            hashes_matched = result['hashes_matched_in_input']
            input_confidence = result['input_confidence']
            fingerprinted_confidence = result['fingerprinted_confidence']
            offset = result['offset']
            offset_seconds = result['offset_seconds']
            match_total = (hashes_matched / total_hashes) * 100
            match_db = (hashes_matched / hashes_in_db) * 100

            self.results_tree.insert("", "end", values=(
                song_id, song_name, total_hashes, hashes_in_db, hashes_matched,
                input_confidence, fingerprinted_confidence, offset, offset_seconds,
                f"{match_total:.2f}%", f"{match_db:.2f}%"
            ))


class DurationAndFileNameDialog(simpledialog.Dialog):
    def __init__(self, parent):
        self.duration = 20
        self.file_name = None
        super().__init__(parent, "Recording Details...")

    def body(self, parent):
        # tk.Label(parent, text="Enter recording duration (seconds):").pack()
        tk.Label(parent, text="Recording Fill size will be 20 sec   ").pack()
        # self.duration_entry = tk.Entry(parent)
        # self.duration_entry.pack()

        tk.Label(parent, text="Enter file name for the recording:").pack()
        self.file_name_entry = tk.Entry(parent)
        self.file_name_entry.pack()

        # return self.duration_entry

    def apply(self):
        # self.duration = int(self.duration_entry.get())
        self.file_name = self.file_name_entry.get()


if __name__ == "__main__":
    root = tk.Tk()
    app = DejavuApp(root)
    root.mainloop()
