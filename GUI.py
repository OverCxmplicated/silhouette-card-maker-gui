
import customtkinter as ctk
from tkinter import messagebox, filedialog
import tkinter as tk  # kept for scrolledtext + menu
from tkinter import scrolledtext
import subprocess
import sys
import os
import threading
import time
import glob
import shutil
from PIL import Image

# -----------------------------
# Project configuration
# -----------------------------
PROJECT_FOLDER_NAME = "silhouette-card-maker-1.2.0"
PROJECT_VERSION = PROJECT_FOLDER_NAME.split("-")[-1]

# -----------------------------
# CustomTkinter global styling
# -----------------------------
ctk.set_appearance_mode("dark")   # "light", "dark", "system"
ctk.set_default_color_theme("green")  # "blue", "green", "dark-blue"


# -----------------------------
# Helper: LabelFrame-like CTk
# -----------------------------
class CTkLabelFrame(ctk.CTkFrame):
    def __init__(self, master=None, text="", corner_radius=8, label_font=None,
                 label_padx=0, label_pady=5, fg_color=None, **kwargs):
        super().__init__(master, corner_radius=corner_radius, fg_color=fg_color, **kwargs)
        if label_font is None:
            label_font = ctk.CTkFont(family="Arial", size=14, weight="bold")
        self.label = ctk.CTkLabel(self, text=text, font=label_font)
        self.label.pack(anchor="w", padx=label_padx, pady=(label_pady, 10))


# -----------------------------
# Main GUI
# -----------------------------
class CardMakerGUI:
    # Centralized game -> method mapping.
    # Each game has a 'dir' used for plugin folder, and a set of human-friendly method labels mapping to 'source' strings.
    GAMES = {
        "Magic: The Gathering": {
            "dir": "mtg",
            "methods": {
                "Moxfield": "moxfield",
                "MTGA": "mtga",
                "MTGO": "mtgo",
                "Archidekt": "archidekt",
                "Deckstats": "deckstats",
                "Scryfall": "scryfall",
            },
        },
        "Riftbound": {
            "dir": "riftbound",
            "methods": {
                "Pixelborn": "pixelborn",
                "TTS": "tts",
                "Piltover": "piltover_archive",
            },
        },
        "Yu-Gi-Oh!": {
            "dir": "yugioh",
            "methods": {
                "YDK": "ydk",
                "YDKE": "ydke",
            },
        },
        "Lorcana": {
            "dir": "lorcana",
            "methods": {
                "Dreamborn": "dreamborn",
            },
        },
        "Altered": {
            "dir": "altered",
            "methods": {
                "Ajordat": "ajordat",
            },
        },
    }

    def __init__(self, root):
        self.root = root
        self.root.title(f"Silhouette Card Maker GUI | loaded {PROJECT_VERSION}")
        self.root.geometry("1000x900")

        # Supported image extensions (Pillow capable)
        self.supported_image_extensions = {
            ".png",".jpg",".jpeg",".gif",".bmp",".tiff",".tif",
            ".webp",".ico",".ppm",".pgm",".pbm",".pnm",".pcx",
            ".dib",".eps",".ps",".pdf",".sgi",".tga",".xbm",".xpm"
        }

        # Paths (discovered later)
        self.project_path = None
        self.venv_path = None
        self.decklist_path = None
        self.front_dir = None
        self.double_sided_dir = None
        self.output_dir = None

        # State
        self.current_step = 0
        self.steps_completed = []
        self.is_running = False

        # Loading animations
        self._loading_running = False
        self._pdf_loading_running = False

        self._thumbnails_refs = []  # keep image refs alive

        self.setup_ui()
        self.check_initial_state()

    # -------------- UI LAYOUT --------------
    def setup_ui(self):
        main_frame = ctk.CTkFrame(self.root, corner_radius=0)
        main_frame.pack(fill="both", expand=True)

        title_label = ctk.CTkLabel(main_frame, text="Silhouette Card Maker Workflow",
                                   font=ctk.CTkFont(size=24, weight="bold"))
        title_label.pack(pady=(20, 30))

        # Progress
        progress_frame = ctk.CTkFrame(main_frame, corner_radius=8)
        progress_frame.pack(fill="x", padx=20, pady=(0, 20))

        ctk.CTkLabel(progress_frame, text="Workflow Progress",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(15, 10))

        self.progress_bar = ctk.CTkProgressBar(progress_frame, width=500, height=16)
        self.progress_bar.pack(pady=(0, 10))
        self.progress_bar.set(0)

        self.status_var = ctk.StringVar(value="Ready to start workflow")
        ctk.CTkLabel(progress_frame, textvariable=self.status_var,
                     font=ctk.CTkFont(size=12)).pack(pady=(0, 15))

        # Steps
        steps_frame = ctk.CTkFrame(main_frame, corner_radius=8)
        steps_frame.pack(fill="x", padx=20, pady=(0, 20))
        self.setup_steps_ui(steps_frame)

        # Output log
        output_frame = ctk.CTkFrame(main_frame, corner_radius=8)
        output_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        ctk.CTkLabel(output_frame, text="Output Log",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(15, 10))

        text_frame = ctk.CTkFrame(output_frame)
        text_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        self.output_text = scrolledtext.ScrolledText(
            text_frame,
            height=10,
            bg="#212121",
            fg="#ffffff",
            insertbackground="#ffffff",
            selectbackground="#1f538d",
            font=("Consolas", 10)
        )
        self.output_text.pack(fill="both", expand=True, padx=5, pady=5)

        # Controls
        control_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        control_frame.pack(pady=(0, 20))

        self.start_button = ctk.CTkButton(
            control_frame, text="Start Workflow",
            command=self.start_workflow,
            font=ctk.CTkFont(size=14, weight="bold"),
            width=160, height=38
        )
        self.start_button.pack(side="left", padx=(0, 15))

        self.reset_button = ctk.CTkButton(
            control_frame, text="Reset",
            command=self.reset_workflow,
            font=ctk.CTkFont(size=14),
            width=100, height=38
        )
        self.reset_button.pack(side="left", padx=(0, 15))

        self.clear_log_button = ctk.CTkButton(
            control_frame, text="Clear Log",
            command=self.clear_log,
            font=ctk.CTkFont(size=14),
            width=120, height=38
        )
        self.clear_log_button.pack(side="left")

    def setup_steps_ui(self, parent):
        ctk.CTkLabel(parent, text="Workflow Steps",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(15, 20))

        self.step_labels = []
        steps = [
            "1. Navigate to project directory",
            "2. Create virtual environment",
            "3. Activate venv & install requirements",
            "4. Clean image directories",
            "5. Choose input method (decklist or upload)",
            "6. Download/process images",
            "7. Create PDF (optional)"
        ]

        steps_container = ctk.CTkFrame(parent, fg_color="transparent")
        steps_container.pack(fill="x", padx=15, pady=(0, 15))

        for step in steps:
            row = ctk.CTkFrame(steps_container, fg_color="transparent")
            row.pack(fill="x", pady=1)

            status_label = ctk.CTkLabel(row, text="⏳", font=ctk.CTkFont(size=16))
            status_label.pack(side="left", padx=(10, 15))

            txt = ctk.CTkLabel(row, text=step, anchor="w", font=ctk.CTkFont(size=12))
            txt.pack(side="left", fill="x", expand=True)
            self.step_labels.append((status_label, txt))

    # -------------- UTILITIES --------------
    def update_step_status(self, step_index, status):
        icons = {'pending': '⏳', 'running': '🔄', 'completed': '✅', 'error': '❌'}
        if 0 <= step_index < len(self.step_labels):
            self.step_labels[step_index][0].configure(text=icons.get(status, '⏳'))

    def log_message(self, message):
        timestamp = time.strftime("%H:%M:%S")
        self.output_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.output_text.see(tk.END)
        self.root.update_idletasks()

    def clear_log(self):
        self.output_text.delete(1.0, tk.END)

    def get_image_pattern_for_directory(self, directory):
        patterns = []
        for ext in self.supported_image_extensions:
            patterns.append(os.path.join(directory, f"*{ext}"))
            patterns.append(os.path.join(directory, f"*{ext.upper()}"))
        return patterns

    def get_all_image_files_in_directory(self, directory):
        if not os.path.exists(directory):
            return []
        image_files = []
        for pattern in self.get_image_pattern_for_directory(directory):
            image_files.extend(glob.glob(pattern))
        return list(set(image_files))

    # -------------- INITIAL CHECKS --------------
    def check_initial_state(self):
        self.log_message("Checking initial project state...")
        self.project_path = self.find_project_directory()

        if not self.project_path:
            self.log_message("Could not find silhouette-card-maker directory")
            self.log_message("Please ensure the project is extracted and accessible.")
            return

        self.venv_path = os.path.join(self.project_path, "venv")
        self.decklist_path = os.path.join(self.project_path, "game", "decklist", "my_decklist.txt")
        self.front_dir = os.path.join(self.project_path, "game", "front")
        self.double_sided_dir = os.path.join(self.project_path, "game", "double_sided")
        self.output_dir = os.path.join(self.project_path, "game", "output")

        self.log_message(f"✓ Project directory: {self.project_path}")
        if os.path.exists(self.venv_path):
            self.log_message("✓ Virtual environment already exists")
            self.update_step_status(1, 'completed')
        else:
            self.log_message("○ Virtual environment needs to be created")

    def validate_project_directory(self, path):
        if not os.path.exists(path):
            return False
        expected_items = ["game", "plugins", "create_pdf.py"]
        for item in expected_items:
            if not os.path.exists(os.path.join(path, item)):
                return False
        return True

    def find_project_directory(self):
        project_folder_name = PROJECT_FOLDER_NAME
        search_locations = [
            os.getcwd(),
            os.path.expanduser("~"),
            os.path.join(os.path.expanduser("~"), "Downloads"),
            os.path.join(os.path.expanduser("~"), "Documents"),
            os.path.join(os.path.expanduser("~"), "Desktop"),
            os.path.join(os.path.expanduser("~"), "Projects"),
            os.path.join(os.path.expanduser("~"), "Workspace"),
            os.path.dirname(os.getcwd()),
            os.path.dirname(os.path.dirname(os.getcwd())),
        ]

        extended = []
        for loc in search_locations:
            extended.append(loc)
            try:
                if os.path.exists(loc):
                    for item in os.listdir(loc):
                        p = os.path.join(loc, item)
                        if os.path.isdir(p):
                            extended.append(p)
            except Exception:
                continue

        for loc in extended:
            if not loc or not os.path.exists(loc):
                continue

            candidate = os.path.join(loc, project_folder_name)
            if os.path.exists(candidate) and self.validate_project_directory(candidate):
                self.log_message(f"Found project directory: {candidate}")
                return candidate

            if os.path.basename(loc) == project_folder_name and self.validate_project_directory(loc):
                self.log_message(f"Found project directory: {loc}")
                return loc

            nested = os.path.join(candidate, project_folder_name)
            if os.path.exists(nested) and self.validate_project_directory(nested):
                self.log_message(f"Found project directory (nested): {nested}")
                return nested

        self.log_message(f"Could not find '{project_folder_name}' in common locations.")
        return None

    # -------------- WORKFLOW --------------
    def start_workflow(self):
        if self.is_running:
            messagebox.showwarning("Warning", "Workflow is already running!")
            return
        if not self.project_path:
            messagebox.showerror("Project Not Found",
                                 "Could not find 'silhouette-card-maker' directory.\n\n"
                                 "Please ensure the project is extracted and accessible.")
            return
        self.is_running = True
        self.start_button.configure(state="disabled")

        t = threading.Thread(target=self.run_workflow, daemon=True)
        t.start()

    def run_workflow(self):
        try:
            self.execute_step_1()
            self.execute_step_2()
            self.execute_step_3()
            self.execute_step_4()
            self.root.after(0, self.execute_step_5_main_thread)
        except Exception as e:
            self.log_message(f"Workflow failed: {e}")
            self.status_var.set("Workflow failed")
            self.is_running = False
            self.root.after(0, lambda: self.start_button.configure(state='normal'))

    # Step 1
    def execute_step_1(self):
        self.root.after(0, lambda: self.update_step_status(0, 'running'))
        self.root.after(0, lambda: self.status_var.set("Navigating to project directory..."))

        if not self.project_path or not os.path.exists(self.project_path):
            raise Exception("Project directory not found or not accessible")

        os.chdir(self.project_path)
        self.log_message(f"✓ Changed to project directory: {os.getcwd()}")
        self.root.after(0, lambda: self.update_step_status(0, 'completed'))
        self.root.after(0, lambda: self.progress_bar.set(0.14))

    # Step 2
    def execute_step_2(self):
        self.root.after(0, lambda: self.update_step_status(1, 'running'))
        self.root.after(0, lambda: self.status_var.set("Creating virtual environment..."))

        if not os.path.exists(self.venv_path):
            self.log_message("Creating virtual environment...")
            result = subprocess.run([sys.executable, "-m", "venv", "venv"],
                                    capture_output=True, text=True, cwd=self.project_path)
            if result.returncode != 0:
                raise Exception(f"Failed to create virtual environment: {result.stderr}")
            self.log_message("✓ Virtual environment created successfully")
        else:
            self.log_message("✓ Virtual environment already exists")

        self.root.after(0, lambda: self.update_step_status(1, 'completed'))
        self.root.after(0, lambda: self.progress_bar.set(0.28))

    # Step 3
    def execute_step_3(self):
        self.root.after(0, lambda: self.update_step_status(2, 'running'))
        self.root.after(0, lambda: self.status_var.set("Configuring virtual environment..."))

        if os.name == "nt":
            venv_python = os.path.join(self.venv_path, "Scripts", "python.exe")
        else:
            venv_python = os.path.join(self.venv_path, "bin", "python")
        if not os.path.exists(venv_python):
            raise Exception("Virtual environment Python executable not found")

        self.venv_python = venv_python
        self.log_message("✓ Virtual environment configured for use")

        self.root.after(0, lambda: self.status_var.set("Installing requirements..."))
        requirements_path = os.path.join(self.project_path, "requirements.txt")
        if not os.path.exists(requirements_path):
            self.log_message("Warning: requirements.txt not found, skipping package installation")
        else:
            cmd = [self.venv_python, "-m", "pip", "install", "-r", "requirements.txt"]
            self.log_message(f"Running: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.project_path)
            if result.stdout:
                for line in result.stdout.strip().splitlines():
                    if line.strip():
                        self.log_message(f"pip: {line}")
            if result.stderr:
                for line in result.stderr.strip().splitlines():
                    if line.strip() and not line.startswith("WARNING"):
                        self.log_message(f"pip error: {line}")
            if result.returncode != 0:
                raise Exception(f"pip install failed with exit code: {result.returncode}")
            self.log_message("✓ Requirements installed successfully")

        self.root.after(0, lambda: self.update_step_status(2, 'completed'))
        self.root.after(0, lambda: self.progress_bar.set(0.42))

    # Step 4
    def execute_step_4(self):
        self.root.after(0, lambda: self.update_step_status(3, 'running'))
        self.root.after(0, lambda: self.status_var.set("Cleaning image files..."))

        directories = [self.front_dir, self.double_sided_dir]
        total_deleted = 0
        for directory in directories:
            if os.path.exists(directory):
                image_files = self.get_all_image_files_in_directory(directory)
                for image_file in image_files:
                    try:
                        os.remove(image_file)
                        total_deleted += 1
                    except Exception as e:
                        self.log_message(f"Warning: Could not delete {image_file}: {e}")
                self.log_message(f"✓ Cleaned {len(image_files)} image files from {directory}")
            else:
                self.log_message(f"Warning: Directory not found: {directory}")
        self.log_message(f"✓ Total image files deleted: {total_deleted}")

        self.root.after(0, lambda: self.update_step_status(3, 'completed'))
        self.root.after(0, lambda: self.progress_bar.set(0.56))

    # Step 5 (main thread)
    def execute_step_5_main_thread(self):
        self.update_step_status(4, 'running')
        self.status_var.set("Choose input method...")
        self.log_message("Waiting for user to choose input method...")

        choice, plugin_info = self.get_input_method_choice()
        if choice == "upload":
            try:
                uploaded_count = self.upload_card_images()
                if uploaded_count == 0:
                    raise Exception("No images were uploaded")
                self.log_message(f"✓ {uploaded_count} images uploaded successfully")
                self.input_method = "upload"
                self.update_step_status(4, 'completed')
                self.progress_bar.set(0.70)
                threading.Thread(target=self.execute_step_6, daemon=True).start()
            except Exception as e:
                self.log_message(f"Step 5 failed: {e}")
                self.status_var.set("Workflow failed")
                self.is_running = False
                self.start_button.configure(state='normal')
        elif choice == "plugin":
            try:
                self.log_message(f"Selected: {plugin_info.get('game')} · {plugin_info.get('method')}")
                decklist_content = self.get_decklist_input()
                if not decklist_content:
                    raise Exception("No decklist provided")
                os.makedirs(os.path.dirname(self.decklist_path), exist_ok=True)
                with open(self.decklist_path, "w", encoding="utf-8") as f:
                    f.write(decklist_content)
                self.log_message(f"✓ Decklist file created: {self.decklist_path}")
                self.input_method = "plugin"
                self.selected_dir = plugin_info["dir"]
                self.selected_source = plugin_info["src"]
                self.update_step_status(4, 'completed')
                self.progress_bar.set(0.70)
                threading.Thread(target=self.execute_step_6, daemon=True).start()
            except Exception as e:
                self.log_message(f"Step 5 failed: {e}")
                self.status_var.set("Workflow failed")
                self.is_running = False
                self.start_button.configure(state='normal')
        else:
            self.log_message("No input method selected - workflow cancelled")
            self.status_var.set("Workflow cancelled")
            self.is_running = False
            self.start_button.configure(state='normal')

    # -------------- Input Method Windows --------------
    def get_input_method_choice(self):
        win = ctk.CTkToplevel(self.root)
        win.title("Choose Input Method")
        win.geometry("700x640")
        win.transient(self.root)
        win.grab_set()
        win.resizable(True, True)

        container = ctk.CTkFrame(win, corner_radius=0)
        container.pack(fill="both", expand=True, padx=25, pady=25)

        ctk.CTkLabel(container, text="Choose Your Input Method",
                     font=ctk.CTkFont(family="Arial", size=18, weight="bold")).pack(pady=(0, 10))

        ctk.CTkLabel(container, text="How would you like to provide your card images?",
                     font=ctk.CTkFont(family="Arial", size=12)).pack(pady=(0, 20))

        result = {"choice": None, "plugin": None}

        # Upload images
        upload_frame = ctk.CTkFrame(container, corner_radius=8)
        upload_frame.pack(fill="x", pady=(0, 15), padx=10)
        ctk.CTkLabel(upload_frame, text="Option 1: Upload Images",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", pady=(8, 5), padx=10)
        for txt in [
            "• Upload your own card image files",
            "• Separate uploads for front and double-faced cards",
            "• Works offline with your existing images",
        ]:
            ctk.CTkLabel(upload_frame, text=txt, font=ctk.CTkFont(size=11)).pack(anchor="w", padx=16)
        ctk.CTkButton(upload_frame, text="📁 Upload Images", command=lambda: (result.__setitem__("choice","upload"), win.destroy())).pack(pady=10)

        # Plugin
        plugin_frame = CTkLabelFrame(container, text="Option 2: Download from Plugin")
        plugin_frame.pack(fill="x", pady=(0, 15), padx=10)
        for txt in [
            "• Enter a text decklist for automatic download",
            "• Images will be downloaded automatically",
            "• Requires internet connection",
        ]:
            ctk.CTkLabel(plugin_frame, text=txt, font=ctk.CTkFont(size=11)).pack(anchor="w", padx=10)

        dropdowns = ctk.CTkFrame(plugin_frame, fg_color="transparent")
        dropdowns.pack(fill="x", padx=10, pady=(6, 10))

        # Game dropdown
        ctk.CTkLabel(dropdowns, text="Game:", font=ctk.CTkFont(size=11)).grid(row=0, column=0, sticky="w", pady=(0,6))
        game_var = ctk.StringVar(value="Magic: The Gathering")
        game_combo = ctk.CTkComboBox(dropdowns, variable=game_var, values=list(self.GAMES.keys()), width=260, state="readonly")
        game_combo.grid(row=0, column=1, sticky="w", padx=(8,0), pady=(0,6))

        # Method dropdown (depends on game)
        ctk.CTkLabel(dropdowns, text="Import method:", font=ctk.CTkFont(size=11)).grid(row=1, column=0, sticky="w")
        method_var = ctk.StringVar(value="Moxfield")
        method_combo = ctk.CTkComboBox(dropdowns, variable=method_var, values=list(self.GAMES[game_var.get()]["methods"].keys()), width=260, state="readonly")
        method_combo.grid(row=1, column=1, sticky="w", padx=(8,0))

        dropdowns.grid_columnconfigure(2, weight=1)

        def update_methods(*_):
            game = game_var.get()
            methods = list(self.GAMES[game]["methods"].keys())
            method_combo.configure(values=methods)
            # Keep selection valid
            if method_var.get() not in methods:
                method_var.set(methods[0] if methods else "")

        game_var.trace_add("write", update_methods)

        def choose_plugin():
            game = game_var.get()
            method_label = method_var.get()
            plug_dir = self.GAMES[game]["dir"]
            plug_src = self.GAMES[game]["methods"][method_label]
            result["choice"] = "plugin"
            result["plugin"] = {"game": game, "method": method_label, "dir": plug_dir, "src": plug_src}
            win.destroy()

        ctk.CTkButton(plugin_frame, text="📝 Use Plugin Download", command=choose_plugin).pack(pady=10)
        ctk.CTkButton(container, text="Cancel", command=win.destroy).pack(pady=(10,0))

        win.wait_window()
        return result["choice"], (result["plugin"] or {})

    def upload_card_images(self):
        win = ctk.CTkToplevel(self.root)
        win.title("Upload Card Images")
        win.geometry("520x600")
        win.transient(self.root)
        win.grab_set()

        frame = ctk.CTkFrame(win, corner_radius=8)
        frame.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(frame, text="Upload Card Images",
                     font=ctk.CTkFont(size=18, weight="bold")).pack(pady=(0, 20))

        ctk.CTkLabel(frame, text="Upload your card image files to the appropriate folders:",
                     font=ctk.CTkFont(size=12)).pack(pady=(0, 20))

        os.makedirs(self.front_dir, exist_ok=True)
        os.makedirs(self.double_sided_dir, exist_ok=True)

        upload_counts = {"front": 0, "double_sided": 0}

        front_frame = CTkLabelFrame(frame, text="Single-Faced Cards")
        front_frame.pack(fill="x", pady=(0, 15), padx=10)
        ctk.CTkLabel(front_frame, text="Upload images for regular single-faced cards:",
                     font=ctk.CTkFont(size=13)).pack(anchor="w", padx=10, pady=(0, 10))

        front_status = ctk.CTkLabel(front_frame, text="No files uploaded",
                                    font=ctk.CTkFont(size=12), text_color="gray")
        front_status.pack(anchor="w", padx=10, pady=(0, 10))

        def upload_front_images():
            image_types = [f"*{ext}" for ext in sorted(self.supported_image_extensions)]
            files = filedialog.askopenfilenames(
                title="Select Front Card Images",
                filetypes=[("All image files", " ".join(image_types)),
                           ("PNG files", "*.png"),
                           ("JPEG files", "*.jpg *.jpeg"),
                           ("All files", "*.*")],
                parent=win
            )
            if files:
                count = self.copy_files_to_directory(files, self.front_dir)
                upload_counts["front"] = count
                front_status.configure(text=f"{count} front images uploaded", text_color="green")
                self.log_message(f"✓ Uploaded {count} front card images")

        ctk.CTkButton(front_frame, text="📁 Choose Front Images", command=upload_front_images).pack(pady=(5, 10), padx=10, anchor="w")

        double_frame = CTkLabelFrame(frame, text="Double-Faced Cards")
        double_frame.pack(fill="x", pady=(0, 15), padx=10)
        ctk.CTkLabel(double_frame, text="Upload images for double-faced/flip cards:",
                     font=ctk.CTkFont(size=13)).pack(anchor="w", padx=10, pady=(0, 10))

        double_status = ctk.CTkLabel(double_frame, text="No files uploaded",
                                     font=ctk.CTkFont(size=12), text_color="gray")
        double_status.pack(anchor="w", padx=10, pady=(0, 10))

        def upload_double_images():
            image_types = [f"*{ext}" for ext in sorted(self.supported_image_extensions)]
            files = filedialog.askopenfilenames(
                title="Select Double-Faced Card Images",
                filetypes=[("All image files", " ".join(image_types)),
                           ("PNG files", "*.png"),
                           ("JPEG files", "*.jpg *.jpeg"),
                           ("All files", "*.*")],
                parent=win
            )
            if files:
                count = self.copy_files_to_directory(files, self.double_sided_dir)
                upload_counts["double_sided"] = count
                double_status.configure(text=f"{count} double-faced images uploaded", text_color="green")
                self.log_message(f"✓ Uploaded {count} double-faced card images")

        ctk.CTkButton(double_frame, text="📁 Choose Double-Faced Images", command=upload_double_images).pack(pady=(5, 10), padx=10, anchor="w")

        # Summary line for total loaded
        total_label = ctk.CTkLabel(frame, text="Total loaded: 0 images", font=ctk.CTkFont(size=12))
        total_label.pack(pady=(8,0))

        def update_total():
            total = upload_counts["front"] + upload_counts["double_sided"]
            total_label.configure(text=f"Total loaded: {total} images")

        # Hook into status updates
        def wrap(fn):
            def inner(*a, **kw):
                r = fn(*a, **kw)
                update_total()
                return r
            return inner

        # rebind with wrappers to update totals after each upload
        front_button = [w for w in front_frame.winfo_children() if isinstance(w, ctk.CTkButton)][0]
        double_button = [w for w in double_frame.winfo_children() if isinstance(w, ctk.CTkButton)][0]
        front_button.configure(command=wrap(upload_front_images))
        double_button.configure(command=wrap(upload_double_images))

        btns = ctk.CTkFrame(frame, fg_color="transparent")
        btns.pack(pady=(10, 0))
        total_uploaded = {"val": 0}

        def on_done():
            total = upload_counts["front"] + upload_counts["double_sided"]
            if total == 0:
                messagebox.showwarning("No Images", "Please upload at least one image before continuing.")
                return
            total_uploaded["val"] = total
            win.destroy()

        ctk.CTkButton(btns, text="✅ Done", command=on_done, width=120).pack(side="left", padx=(0,10))
        ctk.CTkButton(btns, text="❌ Cancel", command=win.destroy, width=120).pack(side="left")

        win.wait_window()
        return total_uploaded["val"]

    def copy_files_to_directory(self, source_files, destination_dir):
        copied = 0
        for src in source_files:
            try:
                filename = os.path.basename(src)
                dest = os.path.join(destination_dir, filename)
                if os.path.exists(dest):
                    name, ext = os.path.splitext(filename)
                    counter = 1
                    while os.path.exists(dest):
                        new_name = f"{name}_{counter}{ext}"
                        dest = os.path.join(destination_dir, new_name)
                        counter += 1
                shutil.copy2(src, dest)
                copied += 1
            except Exception as e:
                self.log_message(f"Warning: Could not copy {src}: {e}")
        return copied

    def get_decklist_input(self):
        win = ctk.CTkToplevel(self.root)
        win.title("Enter Decklist")
        win.geometry("700x500")
        win.transient(self.root)
        win.grab_set()

        frame = ctk.CTkFrame(win, corner_radius=8)
        frame.pack(fill="both", expand=True, padx=15, pady=15)

        ctk.CTkLabel(frame, text="Paste your decklist below:",
                     font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", pady=(0, 8))

        text_container = ctk.CTkFrame(frame)
        text_container.pack(fill="both", expand=True, pady=(0, 10))

        text_widget = scrolledtext.ScrolledText(text_container, wrap=tk.WORD)
        text_widget.pack(fill="both", expand=True)

        # context menu
        menu = tk.Menu(text_widget, tearoff=0)
        menu.add_command(label="Cut", command=lambda: text_widget.event_generate("<<Cut>>"))
        menu.add_command(label="Copy", command=lambda: text_widget.event_generate("<<Copy>>"))
        menu.add_command(label="Paste", command=lambda: text_widget.event_generate("<<Paste>>"))
        menu.add_separator()
        def select_all():
            text_widget.tag_add(tk.SEL, "1.0", tk.END)
            text_widget.mark_set(tk.INSERT, "1.0")
            text_widget.see(tk.INSERT)
        menu.add_command(label="Select All", command=select_all)
        text_widget.bind("<Button-3>", lambda e: (menu.tk_popup(e.x_root, e.y_root), menu.grab_release()))
        text_widget.bind("<Control-a>", lambda e: (select_all(), "break"))
        text_widget.bind("<Control-A>", lambda e: (select_all(), "break"))

        btns = ctk.CTkFrame(frame, fg_color="transparent")
        btns.pack(anchor="e", pady=(10,0))

        result = {"content": None}
        def on_ok():
            result["content"] = text_widget.get("1.0", tk.END).strip()
            win.destroy()

        ctk.CTkButton(btns, text="OK", width=90, command=on_ok).pack(side="left", padx=(0,10))
        ctk.CTkButton(btns, text="Cancel", width=90, command=win.destroy).pack(side="left")

        win.wait_window()
        return result["content"]

    # -------------- Step 6: Download/Process Images --------------
    def execute_step_6(self):
        try:
            self.root.after(0, lambda: self.update_step_status(5, 'running'))
            if getattr(self, "input_method", "") == "upload":
                self.root.after(0, lambda: self.status_var.set("Processing uploaded images..."))
                front_images = self.get_all_image_files_in_directory(self.front_dir)
                double_images = self.get_all_image_files_in_directory(self.double_sided_dir)
                total = len(front_images) + len(double_images)
                if total == 0:
                    raise Exception("No uploaded images found")
                self.log_message(f"✓ Found {len(front_images)} front and {len(double_images)} double-faced images")
                self.root.after(0, lambda: self.update_step_status(5, 'completed'))
                self.root.after(0, self.show_thumbnail_preview)
            elif getattr(self, "input_method", "") == "plugin":
                self.root.after(0, lambda: self.status_var.set("Downloading card images..."))
                self.root.after(0, self.show_loading_indicator)

                plug_dir = getattr(self, "selected_dir", None)
                plug_src = getattr(self, "selected_source", None)
                if not plug_dir or not plug_src:
                    raise Exception("Plugin selection missing")

                cmd = [self.venv_python, f"plugins/{plug_dir}/fetch.py", "game/decklist/my_decklist.txt", plug_src]

                self.log_message("Starting card image download...")
                self.log_message(f"Command: {' '.join(cmd)}")

                process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                           text=True, cwd=self.project_path)
                while True:
                    output = process.stdout.readline()
                    if output == "" and process.poll() is not None:
                        break
                    if output:
                        self.root.after(0, lambda msg=output.strip(): self.log_message(msg))

                return_code = process.poll()
                stderr = process.stderr.read()
                if stderr:
                    self.log_message(f"Errors: {stderr}")
                if return_code != 0:
                    raise Exception(f"Download failed with exit code: {return_code}")

                self.log_message("✓ Card images downloaded successfully")
                self.root.after(0, lambda: self.update_step_status(5, 'completed'))
                self.root.after(0, self.show_thumbnail_preview)
            self.root.after(0, lambda: self.progress_bar.set(0.85))
        except Exception as e:
            self.log_message(f"Step 6 failed: {e}")
            self.root.after(0, lambda: self.status_var.set("Workflow failed"))
        finally:
            self.is_running = False
            self.root.after(0, lambda: self.start_button.configure(state='normal'))
            self.root.after(0, self.hide_loading_indicator)

    # ---------- Loading Indicators (CTk) ----------
    def show_loading_indicator(self):
        if getattr(self, "_loading_running", False):
            return
        self._loading_running = True

        self.loading_win = ctk.CTkToplevel(self.root)
        self.loading_win.title("Downloading...")
        self.loading_win.geometry("360x130")
        self.loading_win.transient(self.root)
        self.loading_win.resizable(False, False)

        frame = ctk.CTkFrame(self.loading_win, corner_radius=8)
        frame.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(frame, text="Downloading card images...", font=ctk.CTkFont(size=14)).pack(pady=(0,10))
        self.loading_bar = ctk.CTkProgressBar(frame)
        self.loading_bar.pack(fill="x", padx=5)
        self.loading_bar.set(0)

        # simple indeterminate animation
        def animate(val=[0.0], dir=[1]):
            if not self._loading_running:
                return
            val[0] += 0.02 * dir[0]
            if val[0] >= 1:
                dir[0] = -1
            elif val[0] <= 0:
                dir[0] = 1
            self.loading_bar.set(max(0.0, min(1.0, val[0])))
            self.loading_win.after(20, animate)
        animate()

    def hide_loading_indicator(self):
        if getattr(self, "_loading_running", False):
            self._loading_running = False
            try:
                self.loading_win.destroy()
            except Exception:
                pass

    def show_pdf_loading_indicator(self):
        if getattr(self, "_pdf_loading_running", False):
            return
        self._pdf_loading_running = True

        self.pdf_win = ctk.CTkToplevel(self.root)
        self.pdf_win.title("Creating PDF...")
        self.pdf_win.geometry("380x150")
        self.pdf_win.transient(self.root)
        self.pdf_win.resizable(False, False)

        frame = ctk.CTkFrame(self.pdf_win, corner_radius=8)
        frame.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(frame, text="Creating PDF...", font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(0,5))
        ctk.CTkLabel(frame, text="This may take a few moments depending on card count",
                     font=ctk.CTkFont(size=11)).pack(pady=(0,10))

        self.pdf_bar = ctk.CTkProgressBar(frame)
        self.pdf_bar.pack(fill="x", padx=5)
        self.pdf_bar.set(0)

        def animate(val=[0.0], dir=[1]):
            if not self._pdf_loading_running:
                return
            val[0] += 0.02 * dir[0]
            if val[0] >= 1:
                dir[0] = -1
            elif val[0] <= 0:
                dir[0] = 1
            self.pdf_bar.set(max(0.0, min(1.0, val[0])))
            self.pdf_win.after(20, animate)
        animate()

    def hide_pdf_loading_indicator(self):
        if getattr(self, "_pdf_loading_running", False):
            self._pdf_loading_running = False
            try:
                self.pdf_win.destroy()
            except Exception:
                pass

    # ---------- Thumbnails (CTk Scrollable) ----------
    def show_thumbnail_preview(self):
        image_files = []
        for directory in [self.front_dir, self.double_sided_dir]:
            if os.path.exists(directory):
                for p in self.get_all_image_files_in_directory(directory):
                    rel = os.path.relpath(p, self.project_path)
                    image_files.append((p, rel))

        if not image_files:
            messagebox.showinfo("No Images", "No card images found to preview.")
            self.continue_to_pdf_step()
            return

        win = ctk.CTkToplevel(self.root)
        win.title(f"Card Image Preview - {len(image_files)} images found")
        win.geometry("1200x800")
        win.transient(self.root)
        win.grab_set()

        # Header
        header = ctk.CTkFrame(win)
        header.pack(fill="x", padx=15, pady=(15,10))
        ctk.CTkLabel(header, text="Downloaded Card Images",
                     font=ctk.CTkFont(size=18, weight="bold")).pack(side="left")
        ctk.CTkLabel(header, text=f"Total: {len(image_files)} images",
                     font=ctk.CTkFont(size=13)).pack(side="right")

        # Scrollable thumbnails
        scroll = ctk.CTkScrollableFrame(win, width=1150, height=620)
        scroll.pack(fill="both", expand=True, padx=15, pady=(0,15))

        self.load_thumbnails(scroll, image_files)

        # Buttons
        btns = ctk.CTkFrame(win, fg_color="transparent")
        btns.pack(pady=(0, 15))
        ctk.CTkButton(btns, text="Images Look Good - Create PDF",
                      command=lambda: (win.destroy(), self.continue_to_pdf_step())).pack(side="left", padx=(0,10))
        ctk.CTkButton(btns, text="Re-download Images",
                      command=lambda: (win.destroy(), self.redownload_images())).pack(side="left", padx=(0,10))
        ctk.CTkButton(btns, text="Skip PDF Creation",
                      command=lambda: (win.destroy(), self.skip_pdf_creation())).pack(side="left")

    def load_thumbnails(self, parent, image_files):
        self._thumbnails_refs.clear()
        cols = 4
        for i, (image_path, rel_path) in enumerate(image_files):
            row = i // cols
            col = i % cols

            cell = ctk.CTkFrame(parent, corner_radius=8)
            cell.grid(row=row, column=col, padx=8, pady=8, sticky="nsew")

            try:
                with Image.open(image_path) as img:
                    img_copy = img.copy()
                img_copy.thumbnail((220, 300), Image.Resampling.LANCZOS)
                # Use CTkImage for dark/light support
                cimg = ctk.CTkImage(light_image=img_copy, dark_image=img_copy, size=img_copy.size)
                lbl = ctk.CTkLabel(cell, image=cimg, text="")
                lbl.pack(padx=6, pady=6)
                self._thumbnails_refs.append(cimg)

                info = f"{os.path.basename(image_path)}"
                ctk.CTkLabel(cell, text=info, font=ctk.CTkFont(size=11)).pack(pady=(0,4))

            except Exception as e:
                ctk.CTkLabel(cell, text=f"Error loading image:\n{e}",
                             text_color="red", font=ctk.CTkFont(size=11)).pack(padx=6, pady=6)

    def close_preview_and_continue(self, preview_window):
        preview_window.destroy()
        self.continue_to_pdf_step()

    def redownload_images(self):
        messagebox.showinfo("Re-download", "Restarting image download process...")
        threading.Thread(target=self.redownload_workflow, daemon=True).start()

    def redownload_workflow(self):
        try:
            self.execute_step_4()
            self.execute_step_6()
        except Exception as e:
            self.log_message(f"Re-download failed: {e}")

    def skip_pdf_creation(self):
        self.log_message("PDF creation skipped by user")
        self.update_step_status(6, 'completed')
        self.progress_bar.set(1.0)
        self.status_var.set("Workflow completed - PDF creation skipped")

    def continue_to_pdf_step(self):
        self.execute_step_7()

    # -------------- Step 7 (PDF) --------------
    def execute_step_7(self):
        self.update_step_status(6, 'running')
        self.status_var.set("Opening PDF creation options...")
        options = self.get_pdf_options()
        if options is not None:
            threading.Thread(target=self.create_pdf_threaded, args=(options,), daemon=True).start()
        else:
            self.log_message("PDF creation cancelled by user")
            self.update_step_status(6, 'completed')
            self.progress_bar.set(1.0)
            self.status_var.set("Workflow completed - PDF creation cancelled")

    def create_pdf_threaded(self, options):
        try:
            self.root.after(0, self.show_pdf_loading_indicator)
            self.create_pdf(options)
            self.root.after(0, lambda: self.update_step_status(6, 'completed'))
            self.root.after(0, lambda: self.progress_bar.set(1.0))
            self.root.after(0, lambda: self.status_var.set("Workflow completed successfully!"))
        except Exception as e:
            self.root.after(0, lambda: self.log_message(f"PDF creation failed: {e}"))
            self.root.after(0, lambda: self.update_step_status(6, 'error'))
            self.root.after(0, lambda: self.status_var.set("PDF creation failed"))
        finally:
            self.root.after(0, self.hide_pdf_loading_indicator)

    def get_pdf_options(self):
        win = ctk.CTkToplevel(self.root)
        win.title("PDF Creation Options")
        win.geometry("540x660")
        win.transient(self.root)
        win.grab_set()

        frame = ctk.CTkFrame(win, corner_radius=8)
        frame.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(frame, text="PDF Creation Options",
                     font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(0, 12))

        # Only fronts
        only_fronts_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(frame, text="Only print fronts of cards (--only_fronts)",
                        variable=only_fronts_var).pack(anchor="w", pady=4)

        # PPI
        ppi_row = ctk.CTkFrame(frame, fg_color="transparent")
        ppi_row.pack(fill="x", pady=4)
        ppi_enabled_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(ppi_row, text="Custom PPI:", variable=ppi_enabled_var).pack(side="left")
        ppi_var = ctk.StringVar(value="300")
        ppi_entry = ctk.CTkEntry(ppi_row, textvariable=ppi_var, width=80, state="disabled")
        ppi_entry.pack(side="left", padx=10)
        def toggle_ppi(*_):
            ppi_entry.configure(state="normal" if ppi_enabled_var.get() else "disabled")
        ppi_enabled_var.trace_add("write", toggle_ppi)

        # Quality
        high_quality_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(frame, text="High Quality (--quality 100)",
                        variable=high_quality_var).pack(anchor="w", pady=4)

        # Extended corners
        corners_row = ctk.CTkFrame(frame, fg_color="transparent")
        corners_row.pack(fill="x", pady=4)
        corners_enabled_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(corners_row, text="Extended Corners:", variable=corners_enabled_var).pack(side="left")
        corners_var = ctk.StringVar(value="0")
        corners_entry = ctk.CTkEntry(corners_row, textvariable=corners_var, width=80, state="disabled")
        corners_entry.pack(side="left", padx=10)
        def toggle_corners(*_):
            corners_entry.configure(state="normal" if corners_enabled_var.get() else "disabled")
        corners_enabled_var.trace_add("write", toggle_corners)

        # Paper size
        paper_row = ctk.CTkFrame(frame, fg_color="transparent")
        paper_row.pack(fill="x", pady=4)
        paper_enabled_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(paper_row, text="Custom Paper Size:", variable=paper_enabled_var).pack(side="left")
        paper_var = ctk.StringVar(value="letter")
        paper_combo = ctk.CTkComboBox(paper_row, variable=paper_var,
                                      values=["letter","a4","a3","tabloid","archb"], state="disabled", width=140)
        paper_combo.pack(side="left", padx=10)
        def toggle_paper(*_):
            paper_combo.configure(state="readonly" if paper_enabled_var.get() else "disabled")
        paper_enabled_var.trace_add("write", toggle_paper)

        # Crop
        crop_row = ctk.CTkFrame(frame, fg_color="transparent")
        crop_row.pack(fill="x", pady=4)
        crop_enabled_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(crop_row, text="Crop outer portion:", variable=crop_enabled_var).pack(side="left")
        crop_val = ctk.StringVar(value="6.5")
        crop_unit = ctk.StringVar(value="%")
        crop_entry = ctk.CTkEntry(crop_row, textvariable=crop_val, width=80, state="disabled")
        crop_entry.pack(side="left", padx=6)
        crop_unit_combo = ctk.CTkComboBox(crop_row, variable=crop_unit, values=["%","mm","in"], state="disabled", width=80)
        crop_unit_combo.pack(side="left", padx=6)
        ctk.CTkLabel(crop_row, text="0-100 | %, in, mm", font=ctk.CTkFont(size=11)).pack(side="left", padx=6)
        def toggle_crop(*_):
            st = "normal" if crop_enabled_var.get() else "disabled"
            crop_entry.configure(state=st)
            crop_unit_combo.configure(state=("readonly" if crop_enabled_var.get() else "disabled"))
        crop_enabled_var.trace_add("write", toggle_crop)

        # Load offset
        load_offset_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(frame, text="Load offset (--load_offset)", variable=load_offset_var).pack(anchor="w", pady=4)

        # Card size
        card_row = ctk.CTkFrame(frame, fg_color="transparent")
        card_row.pack(fill="x", pady=4)
        card_size_enabled_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(card_row, text="Card Size:", variable=card_size_enabled_var).pack(side="left")
        card_size_var = ctk.StringVar(value="standard")
        card_combo = ctk.CTkComboBox(card_row, variable=card_size_var,
                                     values=["standard","standard_double","japanese","poker","poker_half",
                                             "bridge","bridge_square","domino","domino_square"],
                                     state="disabled", width=160)
        card_combo.pack(side="left", padx=10)
        def toggle_card(*_):
            card_combo.configure(state="readonly" if card_size_enabled_var.get() else "disabled")
        card_size_enabled_var.trace_add("write", toggle_card)

        # Custom options
        custom = CTkLabelFrame(frame, text="Custom Options")
        custom.pack(fill="x", pady=8)
        ctk.CTkLabel(custom, text="Additional command line options:",
                     font=ctk.CTkFont(size=11)).pack(anchor="w", padx=10, pady=(0,5))
        custom_options_var = ctk.StringVar(value="")
        ctk.CTkEntry(custom, textvariable=custom_options_var, width=420).pack(padx=10, pady=(0,6), fill="x")
        ctk.CTkLabel(custom, text="Example: --name TEXT --output_path TEXT",
                     font=ctk.CTkFont(size=10)).pack(anchor="w", padx=10, pady=(0,6))

        # Buttons
        btns = ctk.CTkFrame(frame, fg_color="transparent")
        btns.pack(pady=(12, 0))

        result = {"options": None}

        def on_create():
            opts = []
            if only_fronts_var.get():
                opts.append("--only_fronts")
            if ppi_enabled_var.get():
                try:
                    val = int(ppi_var.get().strip())
                    opts.extend(["--ppi", str(val)])
                except ValueError:
                    messagebox.showerror("Error", "PPI must be a valid number")
                    return
            if high_quality_var.get():
                opts.extend(["--quality", "100"])
            if corners_enabled_var.get():
                try:
                    val = int(corners_var.get().strip())
                    opts.extend(["--extend_corners", str(val)])
                except ValueError:
                    messagebox.showerror("Error", "Extended corners must be an integer")
                    return
            if paper_enabled_var.get():
                opts.extend(["--paper_size", paper_var.get()])
            if crop_enabled_var.get():
                try:
                    cval = float(crop_val.get().strip())
                except ValueError:
                    messagebox.showerror("Error", "Crop value must be a number")
                    return
                if not (0 <= cval <= 100):
                    messagebox.showerror("Error", "Crop value must be between 0 and 100")
                    return
                unit = crop_unit.get().strip().lower()
                if unit == "%" or unit == "":
                    arg = str(cval)
                elif unit in ("mm","in"):
                    arg = f"{cval}{unit}"
                else:
                    messagebox.showerror("Error", "Crop unit must be '%', 'mm', or 'in'")
                    return
                opts.extend(["--crop", arg])
            if load_offset_var.get():
                opts.append("--load_offset")
            if card_size_enabled_var.get():
                opts.extend(["--card_size", card_size_var.get()])

            if custom_options_var.get().strip():
                import shlex
                try:
                    opts.extend(shlex.split(custom_options_var.get().strip()))
                except ValueError as e:
                    messagebox.showerror("Error", f"Invalid custom options format: {e}")
                    return

            result["options"] = opts
            win.destroy()

        ctk.CTkButton(btns, text="Create PDF", command=on_create, width=140).pack(side="left", padx=(0,10))
        ctk.CTkButton(btns, text="Cancel", command=win.destroy, width=120).pack(side="left")

        win.wait_window()
        return result["options"]

    def create_pdf(self, options):
        self.log_message("Creating PDF...")
        cmd = [self.venv_python, "create_pdf.py"] + options
        self.log_message(f"Command: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.project_path)
        if result.stdout:
            self.log_message(f"Output: {result.stdout}")
        if result.stderr:
            self.log_message(f"Errors: {result.stderr}")
        if result.returncode != 0:
            raise Exception(f"PDF creation failed with exit code: {result.returncode}")

        self.log_message("✅ PDF created successfully!")
        pdf_file = self.find_created_pdf()
        if pdf_file:
            open_now = self.show_pdf_success_dialog(pdf_file)
            if open_now:
                self.open_pdf_file(pdf_file)
        else:
            messagebox.showinfo("Success", "PDF has been created successfully!")

    def find_created_pdf(self):
        search_paths = [self.output_dir, self.project_path, os.path.join(self.project_path, "game")]
        pdfs = []
        for base in search_paths:
            if os.path.exists(base):
                for pattern in ("*.pdf","*.PDF"):
                    pdfs.extend(glob.glob(os.path.join(base, pattern)))
                    pdfs.extend(glob.glob(os.path.join(base, "**", pattern), recursive=True))
        pdfs = list(set(pdfs))
        if not pdfs:
            return None
        latest = max(pdfs, key=os.path.getmtime)
        self.log_message(f"Most recent PDF: {latest}")
        return latest

    def show_pdf_success_dialog(self, pdf_file):
        win = ctk.CTkToplevel(self.root)
        win.title("PDF Created Successfully")
        win.geometry("420x200")
        win.transient(self.root)
        win.grab_set()
        win.resizable(False, False)

        frame = ctk.CTkFrame(win, corner_radius=8)
        frame.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(frame, text="✅ PDF Created Successfully!", font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(0,8))
        ctk.CTkLabel(frame, text=f"File: {os.path.basename(pdf_file)}", font=ctk.CTkFont(size=12)).pack(pady=(0,8))
        ctk.CTkLabel(frame, text="Would you like to open it now?", font=ctk.CTkFont(size=12)).pack(pady=(0,16))

        res = {"open": False}
        def do_open():
            res["open"] = True
            win.destroy()
        def do_skip():
            res["open"] = False
            win.destroy()

        btns = ctk.CTkFrame(frame, fg_color="transparent")
        btns.pack()
        ctk.CTkButton(btns, text="Open PDF", command=do_open, width=120).pack(side="left", padx=(0,10))
        ctk.CTkButton(btns, text="No Thanks", command=do_skip, width=120).pack(side="left")

        win.wait_window()
        return res["open"]

    def open_pdf_file(self, pdf_file):
        try:
            if sys.platform.startswith("darwin"):
                subprocess.run(["open", pdf_file])
            elif os.name == "nt":
                os.startfile(pdf_file)  # type: ignore
            else:
                subprocess.run(["xdg-open", pdf_file])
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open PDF: {e}")

    # -------------- Reset --------------
    def reset_workflow(self):
        self.progress_bar.set(0)
        self.status_var.set("Ready to start workflow")
        for i in range(len(self.step_labels)):
            self.update_step_status(i, "pending")
        self.steps_completed.clear()
        self.is_running = False
        self.start_button.configure(state="normal")
        self.log_message("Workflow reset.")

# -----------------------------
# App entry
# -----------------------------
if __name__ == "__main__":
    root = ctk.CTk()
    app = CardMakerGUI(root)
    root.mainloop()
