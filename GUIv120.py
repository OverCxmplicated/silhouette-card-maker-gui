import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import subprocess
import sys
import os
import threading
import time
import glob
from pathlib import Path
from PIL import Image, ImageTk

class CardMakerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Silhouette Card Maker - Workflow Manager")
        self.root.geometry("900x700")
        
        # Define supported image extensions based on PIL capabilities
        self.supported_image_extensions = {
            '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.tif', 
            '.webp', '.ico', '.ppm', '.pgm', '.pbm', '.pnm', '.pcx',
            '.dib', '.eps', '.ps', '.pdf', '.sgi', '.tga', '.xbm', '.xpm'
        }
        
        # Project paths - initialize as None, will be set when found
        self.project_path = None
        self.venv_path = None
        self.decklist_path = None
        self.front_dir = None
        self.double_sided_dir = None
        self.output_dir = None
        
        # State tracking
        self.current_step = 0
        self.steps_completed = []
        self.is_running = False
        
        self.setup_ui()
        self.check_initial_state()
        
    def setup_ui(self):
        # Main frame with padding
        main_frame = ttk.Frame(self.root, padding="15")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(3, weight=1)
        
        # Title
        title_label = ttk.Label(main_frame, text="Silhouette Card Maker Workflow", 
                               font=('Arial', 18, 'bold'))
        title_label.grid(row=0, column=0, pady=(0, 20))
        
        # Progress frame
        progress_frame = ttk.LabelFrame(main_frame, text="Workflow Progress", padding="10")
        progress_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 15))
        progress_frame.columnconfigure(0, weight=1)
        
        # Progress bar
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, 
                                           maximum=100, length=400)
        self.progress_bar.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # Status label
        self.status_var = tk.StringVar()
        self.status_var.set("Ready to start workflow")
        self.status_label = ttk.Label(progress_frame, textvariable=self.status_var)
        self.status_label.grid(row=1, column=0)
        
        # Steps frame
        steps_frame = ttk.LabelFrame(main_frame, text="Workflow Steps", padding="10")
        steps_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 15))
        
        self.setup_steps_ui(steps_frame)
        
        # Output frame
        output_frame = ttk.LabelFrame(main_frame, text="Output Log", padding="10")
        output_frame.grid(row=3, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        output_frame.columnconfigure(0, weight=1)
        output_frame.rowconfigure(0, weight=1)
        
        self.output_text = scrolledtext.ScrolledText(output_frame, height=15, width=80)
        self.output_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Control buttons frame
        control_frame = ttk.Frame(main_frame)
        control_frame.grid(row=4, column=0, pady=(15, 0))
        
        self.start_button = ttk.Button(control_frame, text="Start Workflow", 
                                      command=self.start_workflow)
        self.start_button.pack(side=tk.LEFT, padx=(0, 10))
        
        self.reset_button = ttk.Button(control_frame, text="Reset", 
                                      command=self.reset_workflow)
        self.reset_button.pack(side=tk.LEFT, padx=(0, 10))
        
        self.clear_log_button = ttk.Button(control_frame, text="Clear Log", 
                                          command=self.clear_log)
        self.clear_log_button.pack(side=tk.LEFT)
        
    def setup_steps_ui(self, parent):
        # Step indicators
        self.step_labels = []
        steps = [
            "1. Navigate to project directory",
            "2. Create virtual environment", 
            "3. Activate virtual environment and install requirements",
            "4. Choose input method (decklist or upload)",
            "5. Clean image directories",
            "6. Download card images / Use uploaded images",
            "7. Create PDF (optional)"
        ]
        
        for i, step in enumerate(steps):
            frame = ttk.Frame(parent)
            frame.grid(row=i, column=0, sticky=(tk.W, tk.E), pady=2)
            frame.columnconfigure(1, weight=1)
            
            # Status icon
            status_label = ttk.Label(frame, text="⏳", font=('Arial', 12))
            status_label.grid(row=0, column=0, padx=(0, 10))
            
            # Step description
            step_label = ttk.Label(frame, text=step)
            step_label.grid(row=0, column=1, sticky=tk.W)
            
            self.step_labels.append((status_label, step_label))
    
    def update_step_status(self, step_index, status):
        """Update step status: 'pending', 'running', 'completed', 'error'"""
        icons = {
            'pending': '⏳',
            'running': '🔄', 
            'completed': '✅',
            'error': '❌'
        }
        
        if step_index < len(self.step_labels):
            self.step_labels[step_index][0].config(text=icons.get(status, '⏳'))
    
    def log_message(self, message):
        """Add message to output log"""
        timestamp = time.strftime("%H:%M:%S")
        self.output_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.output_text.see(tk.END)
        self.root.update_idletasks()
    
    def clear_log(self):
        """Clear the output log"""
        self.output_text.delete(1.0, tk.END)
    
    def get_image_pattern_for_directory(self, directory):
        """Get glob pattern for all supported image types in a directory"""
        patterns = []
        for ext in self.supported_image_extensions:
            # Add both lowercase and uppercase versions
            patterns.extend([
                os.path.join(directory, f"*{ext}"),
                os.path.join(directory, f"*{ext.upper()}")
            ])
        return patterns
    
    def get_all_image_files_in_directory(self, directory):
        """Get all image files in a directory using supported extensions"""
        if not os.path.exists(directory):
            return []
        
        image_files = []
        patterns = self.get_image_pattern_for_directory(directory)
        
        for pattern in patterns:
            image_files.extend(glob.glob(pattern))
        
        # Remove duplicates and return
        return list(set(image_files))
    
    def check_initial_state(self):
        """Check current state of the project"""
        self.log_message("Checking initial project state...")
        
        # Find the project directory
        self.project_path = self.find_project_directory()
        
        if not self.project_path:
            self.log_message("Could not find silhouette-card-maker directory")
            self.log_message("Please ensure the project is extracted and accessible.")
            return
        
        # Set up all paths once project is found
        self.venv_path = os.path.join(self.project_path, "venv")
        self.decklist_path = os.path.join(self.project_path, "game", "decklist", "my_decklist.txt")
        self.front_dir = os.path.join(self.project_path, "game", "front")
        self.double_sided_dir = os.path.join(self.project_path, "game", "double_sided")
        self.output_dir = os.path.join(self.project_path, "game", "output")
        
        self.log_message(f"✓ Project directory: {self.project_path}")
            
        # Check if virtual environment exists
        if os.path.exists(self.venv_path):
            self.log_message("✓ Virtual environment already exists")
            self.update_step_status(1, 'completed')
        else:
            self.log_message("○ Virtual environment needs to be created")
    def find_project_directory(self):
        """Find the silhouette-card-maker-testing-main directory in common locations"""
        project_folder_name = "silhouette-card-maker-1.1.0"

        # Common locations to search
        search_locations = [
            # Current working directory
            os.getcwd(),

            # User's home directory
            os.path.expanduser("~"),

            # Downloads folder
            os.path.join(os.path.expanduser("~"), "Downloads"),

            # Documents folder
            os.path.join(os.path.expanduser("~"), "Documents"),

            # Desktop folder
            os.path.join(os.path.expanduser("~"), "Desktop"),

            # Common project locations
            os.path.join(os.path.expanduser("~"), "Projects"),
            os.path.join(os.path.expanduser("~"), "Workspace"),

            # Parent directories of current location (in case script is run from within project)
            os.path.dirname(os.getcwd()),
            os.path.dirname(os.path.dirname(os.getcwd())),
        ]

        # Also search in subdirectories of common locations
        extended_search_locations = []
        for location in search_locations:
            extended_search_locations.append(location)

            # Add immediate subdirectories
            try:
                if os.path.exists(location):
                    for item in os.listdir(location):
                        item_path = os.path.join(location, item)
                        if os.path.isdir(item_path):
                            extended_search_locations.append(item_path)
            except (PermissionError, OSError):
                continue

        # Search for the project folder
        for search_location in extended_search_locations:
            if not search_location or not os.path.exists(search_location):
                continue

            # Direct match
            potential_path = os.path.join(search_location, project_folder_name)
            if os.path.exists(potential_path) and self.validate_project_directory(potential_path):
                self.log_message(f"Found project directory: {potential_path}")
                return potential_path

            # Check if current location is the project folder
            if os.path.basename(search_location) == project_folder_name and self.validate_project_directory(search_location):
                self.log_message(f"Found project directory: {search_location}")
                return search_location

            # Handle nested structure (silhouette-card-maker-testing-main/silhouette-card-maker-testing-main)
            nested_path = os.path.join(potential_path, project_folder_name)
            if os.path.exists(nested_path) and self.validate_project_directory(nested_path):
                self.log_message(f"Found project directory (nested): {nested_path}")
                return nested_path

        self.log_message(f"Could not find '{project_folder_name}' directory in any common location")
        self.log_message("Searched locations:")
        for location in search_locations:
            self.log_message(f"  - {location}")

        return None

    def validate_project_directory(self, path):
        """Validate that the directory contains expected project files"""
        if not os.path.exists(path):
            return False

        # Check for key project files/directories that should exist
        expected_items = [
            "game",
            "plugins",
            "create_pdf.py"
        ]

        for item in expected_items:
            item_path = os.path.join(path, item)
            if not os.path.exists(item_path):
                return False

        return True
    def start_workflow(self):
        """Start the complete workflow"""
        if self.is_running:
            messagebox.showwarning("Warning", "Workflow is already running!")
            return
        
        # Check if project directory was found
        if not self.project_path:
            messagebox.showerror("Project Not Found", 
                               "Could not find 'silhouette-card-maker' directory.\n\n" +
                               "Please ensure the project is extracted and accessible.")
            return
            
        self.is_running = True
        self.start_button.config(state='disabled')
        
        # Run workflow in separate thread
        thread = threading.Thread(target=self.run_workflow)
        thread.daemon = True
        thread.start()
    
    def run_workflow(self):
        """Execute the complete workflow"""
        try:
            # Step 1: Navigate to directory
            self.execute_step_1()
            
            # Step 2: Create virtual environment
            self.execute_step_2()
            
            # Step 3: Activate virtual environment (conceptual - we'll use full path)
            self.execute_step_3()
            
            # Step 4: Clean image directories FIRST (before user selects input method)
            self.execute_step_4()
            
            # Step 5: Create decklist file OR upload images (handle in main thread)
            self.root.after(0, self.execute_step_5_main_thread)
            
        except Exception as e:
            self.log_message(f"Workflow failed: {str(e)}")
            self.status_var.set("Workflow failed")
            self.is_running = False
            self.root.after(0, lambda: self.start_button.config(state='normal'))
    
    def execute_step_5_main_thread(self):
        """Step 5: Choose input method (called from main thread)"""
        self.update_step_status(4, 'running')
        self.status_var.set("Choose input method...")
        
        self.log_message("Waiting for user to choose input method...")
        
        # Give user choice between upload or plugin download
        choice, plugin = self.get_input_method_choice()
        
        if choice == "upload":
            try:
                # Direct image upload workflow
                uploaded_count = self.upload_card_images()
                if uploaded_count == 0:
                    raise Exception("No images were uploaded")
                
                self.log_message(f"✓ {uploaded_count} images uploaded successfully")
                self.input_method = "upload"
                
                self.update_step_status(4, 'completed')
                self.progress_var.set(70)
                
                # Continue to step 6 in background thread
                threading.Thread(target=self.execute_step_6, daemon=True).start()
                
            except Exception as e:
                self.log_message(f"Step 5 failed: {str(e)}")
                self.status_var.set("Workflow failed")
                self.is_running = False
                self.start_button.config(state='normal')
            
        elif choice == "plugin":
            try:
                # Plugin-based decklist workflow
                self.log_message(f"Selected plugin: {plugin}")
                
                decklist_content = self.get_decklist_input()
                if not decklist_content:
                    raise Exception("No decklist provided")
                
                # Ensure decklist directory exists
                decklist_dir = os.path.dirname(self.decklist_path)
                os.makedirs(decklist_dir, exist_ok=True)
                
                # Write decklist file
                with open(self.decklist_path, 'w', encoding='utf-8') as f:
                    f.write(decklist_content)
                
                self.log_message(f"✓ Decklist file created: {self.decklist_path}")
                self.input_method = "plugin"
                self.selected_plugin = plugin  # Store selected plugin for future use
                
                self.update_step_status(4, 'completed')
                self.progress_var.set(70)
                
                # Continue to step 6 in background thread
                threading.Thread(target=self.execute_step_6, daemon=True).start()
                
            except Exception as e:
                self.log_message(f"Step 5 failed: {str(e)}")
                self.status_var.set("Workflow failed")
                self.is_running = False
                self.start_button.config(state='normal')
            
        else:
            self.log_message("No input method selected - workflow cancelled")
            self.status_var.set("Workflow cancelled")
            self.is_running = False
            self.start_button.config(state='normal')
    
    def execute_step_1(self):
        """Step 1: Navigate to project directory"""
        self.root.after(0, lambda: self.update_step_status(0, 'running'))
        self.root.after(0, lambda: self.status_var.set("Navigating to project directory..."))
        
        if not self.project_path or not os.path.exists(self.project_path):
            raise Exception("Project directory not found or not accessible")
        
        os.chdir(self.project_path)
        self.log_message(f"✓ Changed to project directory: {os.getcwd()}")
        
        self.root.after(0, lambda: self.update_step_status(0, 'completed'))
        self.root.after(0, lambda: self.progress_var.set(14))
    
    def execute_step_2(self):
        """Step 2: Create virtual environment"""
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
        self.root.after(0, lambda: self.progress_var.set(28))
    
    def execute_step_3(self):
        """Step 3: Activate virtual environment and install requirements"""
        self.root.after(0, lambda: self.update_step_status(2, 'running'))
        self.root.after(0, lambda: self.status_var.set("Configuring virtual environment..."))
    
        # We'll use the full path to python in the venv for subsequent commands
        venv_python = os.path.join(self.venv_path, "Scripts", "python.exe")
        if not os.path.exists(venv_python):
            raise Exception("Virtual environment Python executable not found")
    
        self.venv_python = venv_python
        self.log_message("✓ Virtual environment configured for use")
    
        # Install requirements
        self.root.after(0, lambda: self.status_var.set("Installing requirements..."))
        self.log_message("Installing requirements from requirements.txt...")
    
        requirements_path = os.path.join(self.project_path, "requirements.txt")
    
        # Check if requirements.txt exists
        if not os.path.exists(requirements_path):
            self.log_message("Warning: requirements.txt not found, skipping package installation")
        else:
            try:
                # Install requirements using pip
                pip_cmd = [self.venv_python, "-m", "pip", "install", "-r", "requirements.txt"]
                self.log_message(f"Running: {' '.join(pip_cmd)}")
            
                result = subprocess.run(pip_cmd, capture_output=True, text=True, cwd=self.project_path)
            
                if result.stdout:
                    # Log pip output (but keep it concise)
                    stdout_lines = result.stdout.strip().split('\n')
                    for line in stdout_lines:
                        if line.strip():  # Only log non-empty lines
                            self.log_message(f"pip: {line}")
            
                if result.stderr:
                    stderr_lines = result.stderr.strip().split('\n')
                    for line in stderr_lines:
                        if line.strip() and not line.startswith("WARNING"):  # Skip warnings, log errors
                            self.log_message(f"pip error: {line}")
            
                if result.returncode == 0:
                    self.log_message("✓ Requirements installed successfully")
                else:
                    raise Exception(f"pip install failed with exit code: {result.returncode}")
                
            except Exception as e:
                raise Exception(f"Failed to install requirements: {str(e)}")
    
        self.root.after(0, lambda: self.update_step_status(2, 'completed'))
        self.root.after(0, lambda: self.progress_var.set(42))
    
    def execute_step_4(self):
        """Step 4: Clean image directories"""
        self.root.after(0, lambda: self.update_step_status(3, 'running'))
        self.root.after(0, lambda: self.status_var.set("Cleaning image files..."))
        
        directories = [self.front_dir, self.double_sided_dir]
        total_deleted = 0
        
        for directory in directories:
            if os.path.exists(directory):
                # Get all image files in directory
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
        self.root.after(0, lambda: self.progress_var.set(42))
    
    def get_input_method_choice(self):
        """Let user choose between direct upload or plugin-based download"""
        choice_window = tk.Toplevel(self.root)
        choice_window.title("Choose Input Method")
        choice_window.geometry("650x650")
        choice_window.transient(self.root)
        choice_window.grab_set()
        choice_window.resizable(True, True)
        
        # Center the window
        choice_window.geometry("+%d+%d" % (self.root.winfo_rootx() + 125, 
                                         self.root.winfo_rooty() + 100))
        
        # Use grid instead of pack for better control
        choice_window.columnconfigure(0, weight=1)
        choice_window.rowconfigure(0, weight=1)
        
        frame = ttk.Frame(choice_window, padding="25")
        frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        frame.columnconfigure(0, weight=1)
        
        # Title
        ttk.Label(frame, text="Choose Your Input Method", 
                 font=('Arial', 16, 'bold')).grid(row=0, column=0, pady=(0, 20))
        
        # Description
        ttk.Label(frame, text="How would you like to provide your card images?", 
                 font=('Arial', 11)).grid(row=1, column=0, pady=(0, 25))
        
        result = {'choice': None, 'plugin': None}
        
        # Option 1: Upload Images (now first)
        upload_frame = ttk.LabelFrame(frame, text="Option 1: Upload Images", padding="20")
        upload_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 20))
        
        ttk.Label(upload_frame, text="• Upload your own card image files", 
                 font=('Arial', 10)).pack(anchor=tk.W, pady=2)
        ttk.Label(upload_frame, text="• Separate uploads for front and double-faced cards", 
                 font=('Arial', 10)).pack(anchor=tk.W, pady=2)
        ttk.Label(upload_frame, text="• Works offline with your existing images", 
                 font=('Arial', 10)).pack(anchor=tk.W, pady=(2, 15))
        
        def choose_upload():
            result['choice'] = 'upload'
            choice_window.destroy()
        
        ttk.Button(upload_frame, text="📁 Upload Images", 
                  command=choose_upload).pack()
        
        # Option 2: Use Plugin (replaces decklist option)
        plugin_frame = ttk.LabelFrame(frame, text="Option 2: Download from Plugin", padding="20")
        plugin_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=(0, 25))
        
        ttk.Label(plugin_frame, text="• Enter a text decklist for automatic download", 
                 font=('Arial', 10)).pack(anchor=tk.W, pady=2)
        ttk.Label(plugin_frame, text="• Images will be downloaded automatically", 
                 font=('Arial', 10)).pack(anchor=tk.W, pady=2)
        ttk.Label(plugin_frame, text="• Requires internet connection", 
                 font=('Arial', 10)).pack(anchor=tk.W, pady=(2, 10))
        
        # Plugin selection dropdown
        plugin_selection_frame = ttk.Frame(plugin_frame)
        plugin_selection_frame.pack(fill=tk.X, pady=(0, 15))
        
        ttk.Label(plugin_selection_frame, text="Select card game:", 
                 font=('Arial', 10)).pack(anchor=tk.W, pady=(0, 5))
        
        plugin_var = tk.StringVar(value="Magic: The Gathering")
        plugin_combo = ttk.Combobox(plugin_selection_frame, textvariable=plugin_var, 
                                   values=["Magic: The Gathering Moxfield","Magic: The Gathering MTGA","Magic: The Gathering MTGO","Magic: The Gathering Archidekt","Magic: The Gathering Deckstats","Magic: The Gathering Scryfall", "Riftbound Pixelborn", "Riftbound TTS", "Riftbound Piltover", "Yu-Gi-Oh! YDK", "Yu-Gi-Oh! YDKE", "Lorcana", "Altered"], 
                                   state="readonly", width=40)
        plugin_combo.pack(anchor=tk.W)
        
        def choose_plugin():
            result['choice'] = 'plugin'
            result['plugin'] = plugin_var.get()
            choice_window.destroy()
        
        ttk.Button(plugin_frame, text="📝 Use Plugin Download", 
                  command=choose_plugin).pack()
        
        # Cancel button
        def on_cancel():
            choice_window.destroy()
        
        ttk.Button(frame, text="Cancel", command=on_cancel).grid(row=4, column=0, pady=(20, 0))
        
        # Wait for choice
        choice_window.wait_window()
        
        return result['choice'], result.get('plugin')

    def upload_card_images(self):
        """Handle direct image upload to front and double_sided directories"""
        upload_window = tk.Toplevel(self.root)
        upload_window.title("Upload Card Images")
        upload_window.geometry("600x500")
        upload_window.transient(self.root)
        upload_window.grab_set()
        
        # Center the window
        upload_window.geometry("+%d+%d" % (self.root.winfo_rootx() + 150, 
                                         self.root.winfo_rooty() + 100))
        
        frame = ttk.Frame(upload_window, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        ttk.Label(frame, text="Upload Card Images", 
                 font=('Arial', 16, 'bold')).pack(pady=(0, 20))
        
        # Instructions
        instructions = ttk.Label(frame, text="Upload your card image files to the appropriate folders:", 
                               font=('Arial', 11))
        instructions.pack(pady=(0, 20))
        
        # Ensure directories exist
        os.makedirs(self.front_dir, exist_ok=True)
        os.makedirs(self.double_sided_dir, exist_ok=True)
        
        upload_counts = {'front': 0, 'double_sided': 0}
        
        # Front cards section
        front_frame = ttk.LabelFrame(frame, text="Single-Faced Cards", padding="15")
        front_frame.pack(fill=tk.X, pady=(0, 15))
        
        ttk.Label(front_frame, text="Upload images for regular single-faced cards:", 
                 font=('Arial', 10)).pack(anchor=tk.W, pady=(0, 10))
        
        front_status = ttk.Label(front_frame, text="No files uploaded", 
                               font=('Arial', 9), foreground="gray")
        front_status.pack(anchor=tk.W, pady=(0, 10))
        
        def upload_front_images():
            # Create file types list from supported extensions
            image_types = []
            for ext in sorted(self.supported_image_extensions):
                image_types.append(f"*{ext}")
            
            filetypes = [
                ("All image files", " ".join(image_types)),
                ("PNG files", "*.png"),
                ("JPEG files", "*.jpg *.jpeg"),
                ("GIF files", "*.gif"),
                ("BMP files", "*.bmp"),
                ("TIFF files", "*.tiff *.tif"),
                ("WebP files", "*.webp"),
                ("All files", "*.*")
            ]
            
            files = filedialog.askopenfilenames(
                title="Select Front Card Images",
                filetypes=filetypes,
                parent=upload_window
            )
            
            if files:
                count = self.copy_files_to_directory(files, self.front_dir)
                upload_counts['front'] = count
                front_status.config(text=f"{count} front images uploaded", foreground="green")
                self.log_message(f"✓ Uploaded {count} front card images")
        
        ttk.Button(front_frame, text="📁 Choose Front Images", 
                  command=upload_front_images).pack(anchor=tk.W)
        
        # Double-sided cards section
        double_frame = ttk.LabelFrame(frame, text="Double-Faced Cards", padding="15")
        double_frame.pack(fill=tk.X, pady=(0, 20))
        
        ttk.Label(double_frame, text="Upload images for double-faced/flip cards:", 
                 font=('Arial', 10)).pack(anchor=tk.W, pady=(0, 10))
        
        double_status = ttk.Label(double_frame, text="No files uploaded", 
                                font=('Arial', 9), foreground="gray")
        double_status.pack(anchor=tk.W, pady=(0, 10))
        
        def upload_double_images():
            # Create file types list from supported extensions
            image_types = []
            for ext in sorted(self.supported_image_extensions):
                image_types.append(f"*{ext}")
            
            filetypes = [
                ("All image files", " ".join(image_types)),
                ("PNG files", "*.png"),
                ("JPEG files", "*.jpg *.jpeg"),
                ("GIF files", "*.gif"),
                ("BMP files", "*.bmp"),
                ("TIFF files", "*.tiff *.tif"),
                ("WebP files", "*.webp"),
                ("All files", "*.*")
            ]
            
            files = filedialog.askopenfilenames(
                title="Select Double-Faced Card Images",
                filetypes=filetypes,
                parent=upload_window
            )
            
            if files:
                count = self.copy_files_to_directory(files, self.double_sided_dir)
                upload_counts['double_sided'] = count
                double_status.config(text=f"{count} double-faced images uploaded", foreground="green")
                self.log_message(f"✓ Uploaded {count} double-faced card images")
        
        ttk.Button(double_frame, text="📁 Choose Double-Faced Images", 
                  command=upload_double_images).pack(anchor=tk.W)
        
        # Buttons
        button_frame = ttk.Frame(frame)
        button_frame.pack(pady=(20, 0))
        
        total_uploaded = [0]  # Use list for mutable reference
        
        def on_done():
            total = upload_counts['front'] + upload_counts['double_sided']
            if total == 0:
                messagebox.showwarning("No Images", "Please upload at least one image before continuing.")
                return
            
            total_uploaded[0] = total
            upload_window.destroy()
        
        def on_cancel():
            upload_window.destroy()
        
        ttk.Button(button_frame, text="✅ Done", command=on_done).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="❌ Cancel", command=on_cancel).pack(side=tk.LEFT)
        
        # Wait for window to close
        upload_window.wait_window()
        
        return total_uploaded[0]
    
    def copy_files_to_directory(self, source_files, destination_dir):
        """Copy selected files to the destination directory"""
        import shutil
        
        copied_count = 0
        
        for source_file in source_files:
            try:
                # Get filename and create destination path
                filename = os.path.basename(source_file)
                destination_path = os.path.join(destination_dir, filename)
                
                # If file already exists, add a number to make it unique
                if os.path.exists(destination_path):
                    name, ext = os.path.splitext(filename)
                    counter = 1
                    while os.path.exists(destination_path):
                        new_filename = f"{name}_{counter}{ext}"
                        destination_path = os.path.join(destination_dir, new_filename)
                        counter += 1
                
                # Copy the file
                shutil.copy2(source_file, destination_path)
                copied_count += 1
                
            except Exception as e:
                self.log_message(f"Warning: Could not copy {source_file}: {e}")
        
        return copied_count
    
    def get_decklist_input(self):
        """Get decklist input from user"""
        decklist_window = tk.Toplevel(self.root)
        decklist_window.title("Enter Decklist")
        decklist_window.geometry("600x400")
        decklist_window.transient(self.root)
        decklist_window.grab_set()
        
        # Center the window
        decklist_window.geometry("+%d+%d" % (self.root.winfo_rootx() + 50, 
                                           self.root.winfo_rooty() + 50))
        
        frame = ttk.Frame(decklist_window, padding="15")
        frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        decklist_window.columnconfigure(0, weight=1)
        decklist_window.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(1, weight=1)
        
        ttk.Label(frame, text="Paste your decklist below:", 
                 font=('Arial', 12, 'bold')).grid(row=0, column=0, sticky=tk.W, pady=(0, 10))
        
        text_widget = scrolledtext.ScrolledText(frame, height=15, width=70)
        text_widget.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 15))

        # Add right-click context menu for cut/copy/paste
        def show_context_menu(event):
            try:
                context_menu.tk_popup(event.x_root, event.y_root)
            finally:
                context_menu.grab_release()

        def cut_text():
            try:
                text_widget.event_generate("<<Cut>>")
            except tk.TclError:
                pass

        def copy_text():
            try:
                text_widget.event_generate("<<Copy>>")
            except tk.TclError:
                pass

        def paste_text():
            try:
                text_widget.event_generate("<<Paste>>")
            except tk.TclError:
                pass

        def select_all():
            text_widget.tag_add(tk.SEL, "1.0", tk.END)
            text_widget.mark_set(tk.INSERT, "1.0")
            text_widget.see(tk.INSERT)

        # Create context menu
        context_menu = tk.Menu(text_widget, tearoff=0)
        context_menu.add_command(label="Cut", command=cut_text)
        context_menu.add_command(label="Copy", command=copy_text)
        context_menu.add_command(label="Paste", command=paste_text)
        context_menu.add_separator()
        context_menu.add_command(label="Select All", command=select_all)

        # Bind right-click to show context menu
        text_widget.bind("<Button-3>", show_context_menu)  # Right-click on Windows/Linux
        text_widget.bind("<Button-2>", show_context_menu)  # Middle-click on some systems
        text_widget.bind("<Control-Button-1>", show_context_menu)  # Ctrl+click on Mac

        # Also enable standard keyboard shortcuts
        text_widget.bind("<Control-a>", lambda e: select_all())
        text_widget.bind("<Control-A>", lambda e: select_all())
        
        button_frame = ttk.Frame(frame)
        button_frame.grid(row=2, column=0)
        
        result = {'content': None}
        
        def on_ok():
            result['content'] = text_widget.get(1.0, tk.END).strip()
            decklist_window.destroy()
        
        def on_cancel():
            decklist_window.destroy()
        
        ttk.Button(button_frame, text="OK", command=on_ok).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="Cancel", command=on_cancel).pack(side=tk.LEFT)
        
        # Wait for window to close
        decklist_window.wait_window()
        
        return result['content']
    
    def execute_step_6(self):
        """Step 6: Download card images OR process uploaded images"""
        try:
            self.root.after(0, lambda: self.update_step_status(5, 'running'))
            
            if hasattr(self, 'input_method') and self.input_method == "upload":
                # Images were uploaded directly, skip download
                self.root.after(0, lambda: self.status_var.set("Processing uploaded images..."))
                
                # Count uploaded images
                front_images = self.get_all_image_files_in_directory(self.front_dir)
                double_images = self.get_all_image_files_in_directory(self.double_sided_dir)
                
                total_images = len(front_images) + len(double_images)
                
                if total_images == 0:
                    raise Exception("No uploaded images found")
                
                self.log_message(f"✓ Found {len(front_images)} front images and {len(double_images)} double-sided images")
                self.log_message(f"✓ Total: {total_images} images ready for PDF creation")
                
                self.root.after(0, lambda: self.update_step_status(5, 'completed'))
                self.root.after(0, self.show_thumbnail_preview)
                
            elif hasattr(self, 'input_method') and self.input_method == "plugin":
                # Plugin-based download workflow (existing logic)
                self.root.after(0, lambda: self.status_var.set("Downloading card images..."))
                
                # Show loading indicator
                self.root.after(0, self.show_loading_indicator)
                
                # For now, Magic: The Gathering uses the existing moxfield logic
                # In the future, you can add logic here to select different plugins based on self.selected_plugin
                plugin_map = {
                # Add more plugins here
                "Magic: The Gathering Moxfield": ("mtg", "moxfield"),
                "Magic: The Gathering MTGA": ("mtg", "mtga"),
                "Magic: The Gathering MTGO": ("mtg", "mtgo"),
                "Magic: The Gathering Archidekt": ("mtg", "archidekt"),
                "Magic: The Gathering Deckstats": ("mtg", "deckstats"),
                "Magic: The Gathering Scryfall": ("mtg", "scryfall"),
                "Pokémon": ("pokemon", "empty"),
                "Yu-Gi-Oh! YDK": ("yugioh", "ydk"),
                "Yu-Gi-Oh! YDKE": ("yugioh", "ydke"),
                "Lorcana": ("lorcana", "dreamborn"),
                "Altered": ("altered", "ajordat"),
                "Riftbound Pixelborn": ("riftbound", "pixelborn"),
                "Riftbound TTS": ("riftbound", "tts"),
                "Riftbound Piltover": ("riftbound", "piltover_archive"),
                }

                if self.selected_plugin in plugin_map:
                 plugin_dir, plugin_source = plugin_map[self.selected_plugin]
                 cmd = [self.venv_python, f"plugins/{plugin_dir}/fetch.py", "game/decklist/my_decklist.txt", plugin_source]
                else:
                    raise Exception(f"Unsupported plugin selected: {self.selected_plugin}")
                
                self.log_message("Starting card image download...")
                self.log_message(f"Command: {' '.join(cmd)}")
                
                try:
                    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
                                             text=True, cwd=self.project_path)
                    
                    # Read output in real-time
                    while True:
                        output = process.stdout.readline()
                        if output == '' and process.poll() is not None:
                            break
                        if output:
                            self.root.after(0, lambda msg=output.strip(): self.log_message(msg))
                    
                    return_code = process.poll()
                    stderr = process.stderr.read()
                    
                    if stderr:
                        self.log_message(f"Errors: {stderr}")
                    
                    if return_code == 0:
                        self.log_message("✓ Card images downloaded successfully")
                        self.root.after(0, lambda: self.update_step_status(5, 'completed'))
                        
                        # Show thumbnail preview
                        self.root.after(0, self.show_thumbnail_preview)
                    else:
                        raise Exception(f"Download failed with exit code: {return_code}")
                        
                finally:
                    self.root.after(0, self.hide_loading_indicator)
            
            self.root.after(0, lambda: self.progress_var.set(85))
            
        except Exception as e:
            self.log_message(f"Step 6 failed: {str(e)}")
            self.root.after(0, lambda: self.status_var.set("Workflow failed"))
        finally:
            self.is_running = False
            self.root.after(0, lambda: self.start_button.config(state='normal'))
    
    def show_loading_indicator(self):
        """Show loading indicator"""
        self.loading_window = tk.Toplevel(self.root)
        self.loading_window.title("Downloading...")
        self.loading_window.geometry("300x100")
        self.loading_window.transient(self.root)
        self.loading_window.resizable(False, False)
        
        # Center the window
        self.loading_window.geometry("+%d+%d" % (self.root.winfo_rootx() + 300, 
                                                self.root.winfo_rooty() + 200))
        
        frame = ttk.Frame(self.loading_window, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(frame, text="Downloading card images...", 
                 font=('Arial', 12)).pack(pady=(0, 10))
        
        progress = ttk.Progressbar(frame, mode='indeterminate')
        progress.pack(fill=tk.X)
        progress.start()
        
        self.loading_progress = progress
    
    def hide_loading_indicator(self):
        """Hide loading indicator"""
        if hasattr(self, 'loading_window'):
            self.loading_progress.stop()
            self.loading_window.destroy()
    
    def show_pdf_loading_indicator(self):
        """Show loading indicator for PDF creation"""
        self.pdf_loading_window = tk.Toplevel(self.root)
        self.pdf_loading_window.title("Creating PDF...")
        self.pdf_loading_window.geometry("350x120")
        self.pdf_loading_window.transient(self.root)
        self.pdf_loading_window.resizable(False, False)
        
        # Center the window
        self.pdf_loading_window.geometry("+%d+%d" % (self.root.winfo_rootx() + 275, 
                                                    self.root.winfo_rooty() + 200))
        
        frame = ttk.Frame(self.pdf_loading_window, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)
        
        # Main message
        ttk.Label(frame, text="Creating PDF...", 
                 font=('Arial', 12, 'bold')).pack(pady=(0, 5))
        
        # Subtitle
        ttk.Label(frame, text="This may take a few moments depending on card count", 
                 font=('Arial', 9)).pack(pady=(0, 15))
        
        # Progress bar
        pdf_progress = ttk.Progressbar(frame, mode='indeterminate', length=300)
        pdf_progress.pack(fill=tk.X)
        pdf_progress.start(10)  # Slightly faster animation for PDF creation
        
        self.pdf_loading_progress = pdf_progress
        
        # Optional: Add a subtle status update
        status_label = ttk.Label(frame, text="Processing card images into PDF format...", 
                               font=('Arial', 8), foreground='gray')
        status_label.pack(pady=(10, 0))
    
    def hide_pdf_loading_indicator(self):
        """Hide PDF loading indicator"""
        if hasattr(self, 'pdf_loading_window'):
            self.pdf_loading_progress.stop()
            self.pdf_loading_window.destroy()
    
    def show_thumbnail_preview(self):
        """Show thumbnail preview of downloaded card images"""
        # Collect all image files from both directories
        image_files = []
        
        for directory in [self.front_dir, self.double_sided_dir]:
            if os.path.exists(directory):
                image_files_in_dir = self.get_all_image_files_in_directory(directory)
                for image_file in image_files_in_dir:
                    rel_path = os.path.relpath(image_file, self.project_path)
                    image_files.append((image_file, rel_path))
        
        if not image_files:
            messagebox.showinfo("No Images", "No card images found to preview.")
            self.continue_to_pdf_step()
            return
        
        # Create preview window - made much larger
        preview_window = tk.Toplevel(self.root)
        preview_window.title(f"Card Image Preview - {len(image_files)} images found")
        preview_window.geometry("1200x800")  # Increased from 1000x700
        preview_window.transient(self.root)
        preview_window.grab_set()
        
        # Center the window
        preview_window.geometry("+%d+%d" % (self.root.winfo_rootx() - 150, 
                                          self.root.winfo_rooty() - 100))
        
        main_frame = ttk.Frame(preview_window, padding="15")  # More padding
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        preview_window.columnconfigure(0, weight=1)
        preview_window.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)
        
        # Header
        header_frame = ttk.Frame(main_frame)
        header_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 15))
        header_frame.columnconfigure(1, weight=1)
        
        ttk.Label(header_frame, text="Downloaded Card Images", 
                 font=('Arial', 16, 'bold')).grid(row=0, column=0, sticky=tk.W)  # Larger font
        
        ttk.Label(header_frame, text=f"Total: {len(image_files)} images", 
                 font=('Arial', 12)).grid(row=0, column=1, sticky=tk.E)  # Larger font
        
        # Create scrollable frame for thumbnails
        canvas = tk.Canvas(main_frame, bg='white')
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=1, column=1, sticky=(tk.N, tk.S))
        
        # Load and display thumbnails
        self.load_thumbnails(scrollable_frame, image_files, preview_window)
        
        # Buttons frame
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=2, column=0, columnspan=2, pady=(15, 0))
        
        # Make buttons larger
        ttk.Button(button_frame, text="Images Look Good - Create PDF", 
                  command=lambda: self.close_preview_and_continue(preview_window)).pack(side=tk.LEFT, padx=(0, 15))
        
        ttk.Button(button_frame, text="Re-download Images", 
                  command=lambda: self.redownload_images(preview_window)).pack(side=tk.LEFT, padx=(0, 15))
        
        ttk.Button(button_frame, text="Skip PDF Creation", 
                  command=lambda: self.skip_pdf_creation(preview_window)).pack(side=tk.LEFT)
        
        # Bind mousewheel to canvas (cross-platform)
        def _on_mousewheel(event):
            # Windows and MacOS
            if event.delta:
                canvas.yview_scroll(int(-1*(event.delta/120)), "units")
            # Linux
            else:
                if event.num == 4:
                    canvas.yview_scroll(-1, "units")
                elif event.num == 5:
                    canvas.yview_scroll(1, "units")

        # Bind mouse wheel events for different platforms
        canvas.bind("<MouseWheel>", _on_mousewheel)  # Windows and MacOS
        canvas.bind("<Button-4>", _on_mousewheel)    # Linux
        canvas.bind("<Button-5>", _on_mousewheel)    # Linux

        # Also bind to the scrollable frame so scrolling works anywhere in the preview area
        scrollable_frame.bind("<MouseWheel>", _on_mousewheel)
        scrollable_frame.bind("<Button-4>", _on_mousewheel)
        scrollable_frame.bind("<Button-5>", _on_mousewheel)

        # Make sure the canvas can receive focus for mouse events
        canvas.focus_set()    
    def load_thumbnails(self, parent, image_files, preview_window):
        """Load and display thumbnail images in a grid"""
        try:
            # Calculate grid dimensions (4 columns)
            cols = 4
            rows = (len(image_files) + cols - 1) // cols
            
            for i, (image_path, rel_path) in enumerate(image_files):
                row = i // cols
                col = i % cols
                
                # Create frame for each thumbnail
                thumb_frame = ttk.LabelFrame(parent, text="", padding="5")
                thumb_frame.grid(row=row, column=col, padx=5, pady=5, sticky=(tk.W, tk.E, tk.N, tk.S))
                
                try:
                    # Check if file is a valid image by trying to open it
                    with Image.open(image_path) as img:
                        # Calculate thumbnail size maintaining aspect ratio
                        img.thumbnail((200, 280), Image.Resampling.LANCZOS)
                        
                        # Convert to PhotoImage
                        photo = ImageTk.PhotoImage(img)
                        
                        # Create label with image
                        img_label = ttk.Label(thumb_frame, image=photo)
                        img_label.image = photo  # Keep a reference
                        img_label.grid(row=0, column=0)
                        
                        # Add image info
                        info_text = f"Size: {img.size[0]}x{img.size[1]}"
                        ttk.Label(thumb_frame, text=info_text, font=('Arial', 8)).grid(row=1, column=0)
                        
                except Exception as e:
                    # If image can't be loaded, show error
                    ttk.Label(thumb_frame, text=f"Error loading image:\n{str(e)}", 
                             foreground="red", font=('Arial', 8)).grid(row=0, column=0)
                
                # Update progress periodically
                if i % 10 == 0:
                    preview_window.update_idletasks()
                    
        except Exception as e:
            messagebox.showerror("Preview Error", f"Error creating thumbnail preview: {e}")
    
    def close_preview_and_continue(self, preview_window):
        """Close preview window and continue to PDF step"""
        preview_window.destroy()
        self.continue_to_pdf_step()
    
    def redownload_images(self, preview_window):
        """Close preview and restart image download"""
        preview_window.destroy()
        messagebox.showinfo("Re-download", "Restarting image download process...")
        
        # Go back to step 5 (clean directories) and continue
        threading.Thread(target=self.redownload_workflow, daemon=True).start()
    
    def redownload_workflow(self):
        """Re-execute steps 4 and 6 (clean directories and download)"""
        try:
            self.execute_step_4()  # Clean directories (now step 4)
            self.execute_step_6()  # Download images again
        except Exception as e:
            self.log_message(f"Re-download failed: {str(e)}")
    
    def skip_pdf_creation(self, preview_window):
        """Close preview window and skip PDF creation"""
        preview_window.destroy()
        self.log_message("PDF creation skipped by user")
        self.root.after(0, lambda: self.update_step_status(6, 'completed'))
        self.root.after(0, lambda: self.progress_var.set(100))
        self.root.after(0, lambda: self.status_var.set("Workflow completed - PDF creation skipped"))
    
    def continue_to_pdf_step(self):
        """Continue to PDF creation step"""
        # This method will be called after the preview window closes
        # Go directly to PDF options (no double prompt)
        self.execute_step_7()
    
    def execute_step_7(self):
        """Step 7: PDF creation"""
        self.update_step_status(6, 'running')
        self.status_var.set("Opening PDF creation options...")
        
        # Directly get PDF options (no prompt asking if they want to create PDF)
        pdf_options = self.get_pdf_options()
        if pdf_options is not None:
            # Run PDF creation in background thread
            threading.Thread(target=self.create_pdf_threaded, args=(pdf_options,), daemon=True).start()
        else:
            self.log_message("PDF creation cancelled by user")
            self.update_step_status(6, 'completed')
            self.progress_var.set(100)
            self.status_var.set("Workflow completed - PDF creation cancelled")
    
    def create_pdf_threaded(self, options):
        """Create PDF in background thread with proper UI updates"""
        try:
            # Show loading indicator for PDF creation
            self.root.after(0, self.show_pdf_loading_indicator)
            
            self.create_pdf(options)
            self.root.after(0, lambda: self.update_step_status(6, 'completed'))
            self.root.after(0, lambda: self.progress_var.set(100))
            self.root.after(0, lambda: self.status_var.set("Workflow completed successfully!"))
        except Exception as e:
            self.root.after(0, lambda: self.log_message(f"PDF creation failed: {e}"))
            self.root.after(0, lambda: self.update_step_status(6, 'error'))
            self.root.after(0, lambda: self.status_var.set("PDF creation failed"))
        finally:
            # Hide loading indicator
            self.root.after(0, self.hide_pdf_loading_indicator)
    
    def get_pdf_options(self):
        """Get PDF creation options from user"""
        options_window = tk.Toplevel(self.root)
        options_window.title("PDF Creation Options")
        options_window.geometry("500x580")
        options_window.transient(self.root)
        options_window.grab_set()
        
        # Center the window
        options_window.geometry("+%d+%d" % (self.root.winfo_rootx() + 200, 
                                          self.root.winfo_rooty() + 100))
        
        frame = ttk.Frame(options_window, padding="20")
        frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        options_window.columnconfigure(0, weight=1)
        options_window.rowconfigure(0, weight=1)
        
        ttk.Label(frame, text="PDF Creation Options", 
                 font=('Arial', 14, 'bold')).grid(row=0, column=0, columnspan=2, pady=(0, 20))
        
        # Only fronts option
        only_fronts_var = tk.BooleanVar()
        ttk.Checkbutton(frame, text="Only print fronts of cards (--only_fronts)", 
                       variable=only_fronts_var).grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=5)
        
        # PPI option
        ppi_frame = ttk.Frame(frame)
        ppi_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        ppi_frame.columnconfigure(2, weight=1)
        
        ppi_enabled_var = tk.BooleanVar()
        ttk.Checkbutton(ppi_frame, text="Custom PPI:", 
                       variable=ppi_enabled_var).grid(row=0, column=0, sticky=tk.W)
        ppi_var = tk.StringVar(value="300")
        ppi_entry = ttk.Entry(ppi_frame, textvariable=ppi_var, width=10, state='disabled')
        ppi_entry.grid(row=0, column=1, sticky=tk.W, padx=(10, 0))
        
        def toggle_ppi():
            if ppi_enabled_var.get():
                ppi_entry.config(state='normal')
            else:
                ppi_entry.config(state='disabled')
        
        ppi_enabled_var.trace('w', lambda *args: toggle_ppi())
        
        # High quality option
        high_quality_var = tk.BooleanVar()
        ttk.Checkbutton(frame, text="High Quality (--quality 100)", 
                       variable=high_quality_var).grid(row=3, column=0, columnspan=2, sticky=tk.W, pady=5)
        
        # Extended corners option
        corners_frame = ttk.Frame(frame)
        corners_frame.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        corners_frame.columnconfigure(2, weight=1)
        
        corners_enabled_var = tk.BooleanVar()
        ttk.Checkbutton(corners_frame, text="Extended Corners:", 
                       variable=corners_enabled_var).grid(row=0, column=0, sticky=tk.W)
        corners_var = tk.StringVar(value="0")
        corners_entry = ttk.Entry(corners_frame, textvariable=corners_var, width=10, state='disabled')
        corners_entry.grid(row=0, column=1, sticky=tk.W, padx=(10, 0))
        
        def toggle_corners():
            if corners_enabled_var.get():
                corners_entry.config(state='normal')
            else:
                corners_entry.config(state='disabled')
        
        corners_enabled_var.trace('w', lambda *args: toggle_corners())
        
        # Paper size option
        paper_frame = ttk.Frame(frame)
        paper_frame.grid(row=5, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        paper_frame.columnconfigure(2, weight=1)
        
        paper_enabled_var = tk.BooleanVar()
        ttk.Checkbutton(paper_frame, text="Custom Paper Size:", 
                       variable=paper_enabled_var).grid(row=0, column=0, sticky=tk.W)
        paper_var = tk.StringVar(value="letter")
        paper_combo = ttk.Combobox(paper_frame, textvariable=paper_var, values=["letter", "a4", "a3", "tabloid", "archb"],
                                  state="disabled", width=15)
        paper_combo.grid(row=0, column=1, sticky=tk.W, padx=(10, 0))
        
        def toggle_paper():
            if paper_enabled_var.get():
                paper_combo.config(state='readonly')
            else:
                paper_combo.config(state='disabled')
        
        paper_enabled_var.trace('w', lambda *args: toggle_paper())

        # Crop option
        crop_frame = ttk.Frame(frame)
        crop_frame.grid(row=6, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        crop_frame.columnconfigure(2, weight=1)
        
        crop_enabled_var = tk.BooleanVar()
        ttk.Checkbutton(crop_frame, text="Crop outer portion:", 
                       variable=crop_enabled_var).grid(row=0, column=0, sticky=tk.W)
        crop_var = tk.StringVar(value="6.5")
        crop_entry = ttk.Entry(crop_frame, textvariable=crop_var, width=10, state='disabled')
        crop_entry.grid(row=0, column=1, sticky=tk.W, padx=(10, 5))
        crop_type = tk.StringVar(value="%")
        crop_entry2 = ttk.Entry(crop_frame, textvariable=crop_type, width=10, state='disabled')
        crop_entry2.grid(row=0, column=2, sticky=tk.W, padx=(5, 5))
        ttk.Label(crop_frame, text="0-100 | %,in,mm", font=('Arial', 9)).grid(row=0, column=3, sticky=tk.W)
        
        def toggle_crop():
            if crop_enabled_var.get():
                crop_entry.config(state='normal')
                crop_entry2.config(state='normal')
            else:
                crop_entry.config(state='disabled')
                crop_entry2.config(state='disabled')
        
        crop_enabled_var.trace('w', lambda *args: toggle_crop())

        # Load offset option
        load_offset_var = tk.BooleanVar()
        ttk.Checkbutton(frame, text="Load offset (--load_offset)", 
                       variable=load_offset_var).grid(row=7, column=0, columnspan=2, sticky=tk.W, pady=5)

        # Card size option
        card_size_frame = ttk.Frame(frame)
        card_size_frame.grid(row=8, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        card_size_frame.columnconfigure(2, weight=1)
        
        card_size_enabled_var = tk.BooleanVar()
        ttk.Checkbutton(card_size_frame, text="Card Size:", 
                       variable=card_size_enabled_var).grid(row=0, column=0, sticky=tk.W)
        card_size_var = tk.StringVar(value="standard")
        card_size_combo = ttk.Combobox(card_size_frame, textvariable=card_size_var, 
                                      values=["standard", "standard_double", "japanese", "poker", "poker_half", "bridge", "bridge_square", "domino", "domino_square"],
                                      state="disabled", width=15)
        card_size_combo.grid(row=0, column=1, sticky=tk.W, padx=(10, 0))
        
        def toggle_card_size():
            if card_size_enabled_var.get():
                card_size_combo.config(state='readonly')
            else:
                card_size_combo.config(state='disabled')
        
        card_size_enabled_var.trace('w', lambda *args: toggle_card_size())

        # Custom options text box
        custom_frame = ttk.LabelFrame(frame, text="Custom Options", padding="10")
        custom_frame.grid(row=9, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)
        custom_frame.columnconfigure(0, weight=1)
        
        ttk.Label(custom_frame, text="Additional command line options:", 
                 font=('Arial', 9)).grid(row=0, column=0, sticky=tk.W, pady=(0, 5))
        
        custom_options_var = tk.StringVar()
        custom_entry = ttk.Entry(custom_frame, textvariable=custom_options_var, width=50)
        custom_entry.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 5))
        
        ttk.Label(custom_frame, text="Example: --name TEXT --output_path TEXT", 
                 font=('Arial', 8), foreground='gray').grid(row=2, column=0, sticky=tk.W)
        
        # Buttons
        button_frame = ttk.Frame(frame)
        button_frame.grid(row=10, column=0, columnspan=2, pady=(20, 0))
        
        result = {'options': None}
        
        def on_create():
            options = []
            
            if only_fronts_var.get():
                options.append("--only_fronts")
            
            if ppi_enabled_var.get() and ppi_var.get().strip():
                try:
                    ppi_val = int(ppi_var.get().strip())
                    options.extend(["--ppi", str(ppi_val)])
                except ValueError:
                    messagebox.showerror("Error", "PPI must be a valid number")
                    return
            
            if high_quality_var.get():
                options.extend(["--quality", "100"])
            
            if corners_enabled_var.get() and corners_var.get().strip():
                try:
                    corners_val = int(corners_var.get().strip())
                    options.extend(["--extend_corners", str(corners_val)])
                except ValueError:
                    messagebox.showerror("Error", "Extended corners must be a valid number")
                    return
            if paper_enabled_var.get():
                options.extend(["--paper_size", paper_var.get()])
            if crop_enabled_var.get():
                crop_input = crop_var.get().strip()
                crop_unit = crop_type.get().strip().lower()

                # Validate crop value
                if crop_input:
                    try:
                        crop_val = float(crop_input)
                        if not (0 <= crop_val <= 100):
                            messagebox.showerror("Error", "Crop value must be between 0 and 100.")
                            return
                    except ValueError:
                        messagebox.showerror("Error", "Crop value must be a valid number.")
                        return
                else:
                    messagebox.showerror("Error", "Crop value is required.")
                    return

                # Validate crop unit
                if not crop_unit or crop_unit == "%":
                    crop_arg = str(crop_val)  # Just the number
                elif crop_unit in ["mm", "in"]:
                    crop_arg = f"{crop_val}{crop_unit}"
                else:
                    messagebox.showerror("Error", "Crop type must be '%', 'mm', or 'in', or left blank.")
                    return

                # Add to options
                options.extend(["--crop", crop_arg])
            if load_offset_var.get():
                options.append("--load_offset")
            if card_size_enabled_var.get():
                options.extend(["--card_size", card_size_var.get()])
            # Add custom options if provided
            if custom_options_var.get().strip():
                import shlex
                try:
                    # Parse the custom options string properly (handles quoted arguments)
                    custom_opts = shlex.split(custom_options_var.get().strip())
                    options.extend(custom_opts)
                except ValueError as e:
                    messagebox.showerror("Error", f"Invalid custom options format: {e}")
                    return
            
            result['options'] = options
            options_window.destroy()
        
        def on_cancel():
            options_window.destroy()
        
        ttk.Button(button_frame, text="Create PDF", command=on_create).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="Cancel", command=on_cancel).pack(side=tk.LEFT)
        
        # Wait for window to close
        options_window.wait_window()
        
        return result['options']
    
    def create_pdf(self, options):
        """Create PDF with specified options"""
        self.log_message("Creating PDF...")
        
        cmd = [self.venv_python, "create_pdf.py"] + options
        self.log_message(f"Command: {' '.join(cmd)}")
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.project_path)
            
            if result.stdout:
                self.log_message(f"Output: {result.stdout}")
            if result.stderr:
                self.log_message(f"Errors: {result.stderr}")
            
            if result.returncode == 0:
                self.log_message("✅ PDF created successfully!")
                
                # Find the created PDF file
                pdf_file = self.find_created_pdf()
                
                if pdf_file:
                    # Create a simple, reliable custom dialog
                    open_pdf = self.show_simple_pdf_dialog(pdf_file)
                    
                    if open_pdf:
                        self.open_pdf_file(pdf_file)
                else:
                    messagebox.showinfo("Success", "PDF has been created successfully!")
            else:
                raise Exception(f"PDF creation failed with exit code: {result.returncode}")
                
        except Exception as e:
            self.log_message(f"Error creating PDF: {e}")
            messagebox.showerror("Error", f"Failed to create PDF: {e}")
    
    def find_created_pdf(self):
        """Find the most recently created PDF file in the project output directory"""
        try:
            # Primary location where PDFs are created
            pdf_search_paths = [
                self.output_dir,  # game/output directory (most likely location)
                self.project_path,  # Root project directory (fallback)
                os.path.join(self.project_path, "game"),  # Game directory (fallback)
            ]
            
            pdf_files = []
            
            # Search in all possible directories
            for search_path in pdf_search_paths:
                if os.path.exists(search_path):
                    self.log_message(f"Searching for PDFs in: {search_path}")
                    
                    # Search for PDF files (case insensitive)
                    for pattern in ["*.pdf", "*.PDF"]:
                        pattern_path = os.path.join(search_path, pattern)
                        found_files = glob.glob(pattern_path)
                        pdf_files.extend(found_files)
                        
                        # Also search recursively in subdirectories
                        recursive_pattern = os.path.join(search_path, "**", pattern)
                        recursive_files = glob.glob(recursive_pattern, recursive=True)
                        pdf_files.extend(recursive_files)
                    
                    # Log what files are in this directory
                    try:
                        files_in_dir = os.listdir(search_path)
                        self.log_message(f"Files in {search_path}: {files_in_dir}")
                    except:
                        pass
                else:
                    self.log_message(f"Directory does not exist: {search_path}")
            
            # Remove duplicates
            pdf_files = list(set(pdf_files))
            
            if pdf_files:
                self.log_message(f"Found {len(pdf_files)} PDF file(s):")
                for pdf in pdf_files:
                    self.log_message(f"  - {pdf}")
                
                # Return the most recently modified PDF file
                latest_pdf = max(pdf_files, key=os.path.getmtime)
                self.log_message(f"Most recent PDF: {latest_pdf}")
                return latest_pdf
            else:
                self.log_message("No PDF files found in any search location")
                return None
                
        except Exception as e:
            self.log_message(f"Error finding PDF file: {e}")
            return None
    
    def show_simple_pdf_dialog(self, pdf_file):
        """Show a simple PDF success dialog centered on the main window"""
        dialog = tk.Toplevel(self.root)
        dialog.title("PDF Created Successfully")
        dialog.geometry("400x180")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(False, False)
        
        # Calculate position relative to main window
        self.root.update_idletasks()
        main_x = self.root.winfo_x()
        main_y = self.root.winfo_y()
        main_width = self.root.winfo_width()
        main_height = self.root.winfo_height()
        
        # Set dialog size
        dialog_width = 400
        dialog_height = 180
        
        # Calculate center position
        center_x = main_x + (main_width - dialog_width) // 2
        center_y = main_y + (main_height - dialog_height) // 2
        
        # Set geometry
        dialog.geometry(f"{dialog_width}x{dialog_height}+{center_x}+{center_y}")
        
        # Create content with fixed layout
        content_frame = tk.Frame(dialog, padx=20, pady=20)
        content_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = tk.Label(content_frame, text="✅ PDF Created Successfully!", 
                              font=('Arial', 12, 'bold'))
        title_label.pack(pady=(0, 10))
        
        # File info
        file_label = tk.Label(content_frame, text=f"File: {os.path.basename(pdf_file)}", 
                             font=('Arial', 10))
        file_label.pack(pady=(0, 10))
        
        # Question
        question_label = tk.Label(content_frame, text="Would you like to open it now?", 
                                 font=('Arial', 10))
        question_label.pack(pady=(0, 20))
        
        # Result storage
        result = [None]
        
        # Button functions
        def open_pdf():
            result[0] = True
            dialog.destroy()
        
        def skip_open():
            result[0] = False
            dialog.destroy()
        
        # Buttons frame - using tk.Frame for simpler layout
        button_frame = tk.Frame(content_frame)
        button_frame.pack()
        
        # Create buttons with tk.Button for more reliable display
        open_button = tk.Button(button_frame, text="Open PDF", command=open_pdf, 
                               width=10, height=1)
        open_button.pack(side=tk.LEFT, padx=(0, 10))
        
        skip_button = tk.Button(button_frame, text="No Thanks", command=skip_open, 
                               width=10, height=1)
        skip_button.pack(side=tk.LEFT)
        
        # Focus and wait
        open_button.focus_set()
        dialog.wait_window()
        
        return result[0]
    
    def open_pdf_file(self, pdf_path):
        """Open the PDF file with the default system application"""
        try:
            import platform
            
            system = platform.system()
            
            if system == "Windows":
                # Windows
                os.startfile(pdf_path)
            elif system == "Darwin":
                # macOS
                subprocess.run(["open", pdf_path])
            else:
                # Linux
                subprocess.run(["xdg-open", pdf_path])
            
            self.log_message(f"✅ Opened PDF file: {os.path.basename(pdf_path)}")
            
        except Exception as e:
            self.log_message(f"Error opening PDF file: {e}")
            messagebox.showerror("Error", f"Could not open PDF file: {e}\n\nFile location: {pdf_path}")
    
    def reset_workflow(self):
        """Reset the workflow to initial state"""
        if self.is_running:
            messagebox.showwarning("Warning", "Cannot reset while workflow is running!")
            return
        
        # Reset progress
        self.progress_var.set(0)
        self.status_var.set("Ready to start workflow")
        
        # Reset step indicators
        for i in range(len(self.step_labels)):
            self.update_step_status(i, 'pending')
        
        # Reset state
        self.current_step = 0
        self.steps_completed = []
        
        # Clear input method
        if hasattr(self, 'input_method'):
            delattr(self, 'input_method')
        
        self.log_message("Workflow reset to initial state")

def main():
    try:
        root = tk.Tk()
        app = CardMakerGUI(root)
        root.mainloop()
    except Exception as e:
        import traceback
        print("An unhandled exception occurred:")
        traceback.print_exc()
    finally:
        input("Press Enter to exit...")

if __name__ == "__main__":
    main()