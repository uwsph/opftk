import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

#
# Dependency checks
#
try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
except ImportError:
    raise SystemExit(
        "Missing dependency: tkinterdnd2\n\n"
        "Install with:\n"
        "pip install tkinterdnd2"
    )

try:
    from opf import OPF
except ImportError:
    raise SystemExit(
        "Missing dependency: Open Privacy Filter\n\n"
        "Install with:\n"
        "git clone https://github.com/openai/privacy-filter.git\n"
        "cd privacy-filter\n"
        "pip install -e ."
    )

try:
    import torch
except ImportError:
    raise SystemExit(
        "Missing dependency: torch\n\n"
        "Install with:\n"
        "pip install torch"
    )

class OPFGui:

    def __init__(self, root):

        self.root = root

        self.root.title("Open Privacy Filter GUI")
        self.root.geometry("1400x800")

        self.opf = None
        self.model_loaded = False
        self.device = "unknown"

        self.last_directory = os.path.expanduser("~")

        self.build_ui()

    #################################################################
    # UI
    #################################################################

    def build_ui(self):

        toolbar = ttk.Frame(self.root)
        toolbar.pack(fill="x", padx=5, pady=5)

        self.open_button = ttk.Button(
            toolbar,
            text="Open File",
            command=self.open_file
        )
        self.open_button.pack(side="left", padx=2)

        self.redact_button = ttk.Button(
            toolbar,
            text="Redact",
            command=self.start_redaction
        )
        self.redact_button.pack(side="left", padx=2)

        self.clear_button = ttk.Button(
            toolbar,
            text="Clear",
            command=self.clear_all
        )
        self.clear_button.pack(side="left", padx=2)

        self.copy_button = ttk.Button(
            toolbar,
            text="Copy Output",
            command=self.copy_output
        )
        self.copy_button.pack(side="left", padx=2)

        self.save_button = ttk.Button(
            toolbar,
            text="Save Output",
            command=self.save_output
        )
        self.save_button.pack(side="left", padx=2)

        self.about_button = ttk.Button(
            toolbar,
            text="About",
            command=self.show_about
        )
        self.about_button.pack(side="left", padx=2)

        self.progress = ttk.Progressbar(
            toolbar,
            mode="indeterminate",
            length=200
        )

        self.progress.pack(
            side="right",
            padx=10
        )

        paned = ttk.PanedWindow(
            self.root,
            orient=tk.HORIZONTAL
        )

        paned.pack(
            fill="both",
            expand=True,
            padx=5,
            pady=5
        )

        left_frame = ttk.Frame(paned)
        right_frame = ttk.Frame(paned)

        paned.add(left_frame, weight=1)
        paned.add(right_frame, weight=1)

        ttk.Label(
            left_frame,
            text="Input Text"
        ).pack(anchor="w")

        self.input_text = tk.Text(
            left_frame,
            wrap="word",
            undo=True
        )

        self.input_text.pack(
            fill="both",
            expand=True
        )

        ttk.Label(
            right_frame,
            text="Redacted Output"
        ).pack(anchor="w")

        self.output_text = tk.Text(
            right_frame,
            wrap="word"
        )

        self.output_text.pack(
            fill="both",
            expand=True
        )

        self.status_var = tk.StringVar()
        self.status_var.set("Ready")

        status = ttk.Label(
            self.root,
            textvariable=self.status_var,
            relief="sunken",
            anchor="w"
        )

        status.pack(
            fill="x",
            side="bottom"
        )

        self.input_text.drop_target_register(DND_FILES)

        self.input_text.dnd_bind(
            "<<Drop>>",
            self.on_drop
        )

    #################################################################
    # Status
    #################################################################

    def set_status(self, text):

        self.status_var.set(text)

    #################################################################
    # About
    #################################################################

    def show_about(self):

        messagebox.showinfo(
            "About",
            "Open Privacy Filter GUI\n\n"
            "- Front-end for OpenAI's Privacy Filter\n"
            "- Supports drag-and-drop text files\n"
            "- Automatically selects GPU or CPU\n"
            "- Windows, macOS, and Linux compatible\n"
            "- Version: 0.0.4\n"
            "- License: Apache 2.0\n"
            "- URL: https://github.com/uwsph/opftk"
        )

    #################################################################
    # File Loading
    #################################################################

    def open_file(self):

        filename = filedialog.askopenfilename(
            initialdir=self.last_directory,
            filetypes=[
                (
                    "Supported Text Files",
                    "*.txt *.log *.csv *.json *.md"
                ),
                ("All Files", "*.*")
            ]
        )

        if not filename:
            return

        self.last_directory = os.path.dirname(filename)

        self.load_text_file(filename)

    def load_text_file(self, filename):

        try:

            size_mb = os.path.getsize(
                filename
            ) / (1024 * 1024)

            if size_mb > 100:

                if not messagebox.askyesno(
                    "Large File",
                    f"This file is {size_mb:.1f} MB.\n\n"
                    "Continue loading?"
                ):
                    return

            with open(
                filename,
                "r",
                encoding="utf-8-sig",
                errors="replace"
            ) as f:

                content = f.read()

            self.input_text.delete(
                "1.0",
                tk.END
            )

            self.input_text.insert(
                "1.0",
                content
            )

            self.set_status(
                f"Loaded {os.path.basename(filename)}"
            )

        except Exception as ex:

            messagebox.showerror(
                "Open Error",
                str(ex)
            )

    def on_drop(self, event):

        filename = event.data.strip("{}")

        if os.path.isfile(filename):

            self.last_directory = os.path.dirname(
                filename
            )

            self.load_text_file(filename)

    #################################################################
    # OPF
    #################################################################

    def initialize_model(self):

        if self.model_loaded:
            return

        self.root.after(
            0,
            lambda: self.set_status(
                "Initializing OPF. First launch may download model files..."
            )
        )

        try:

            if torch.cuda.is_available():

                #
                # Verify CUDA actually works
                #
                torch.tensor([1.0]).cuda()

                self.device = "cuda"

                gpu_name = torch.cuda.get_device_name(0)

                self.root.after(
                    0,
                    lambda: self.set_status(
                        f"Loading OPF on GPU: {gpu_name}"
                    )
                )

            else:

                self.device = "cpu"

                self.root.after(
                    0,
                    lambda: self.set_status(
                        "Loading OPF on CPU"
                    )
                )

        except Exception:

            self.device = "cpu"

            self.root.after(
                0,
                lambda: self.set_status(
                    "GPU unavailable. Using CPU."
                )
            )

        self.opf = OPF(
            device=self.device,
            output_mode="redacted"
        )

        self.model_loaded = True

    #################################################################
    # Buttons
    #################################################################

    def disable_controls(self):

        self.open_button.config(state="disabled")
        self.redact_button.config(state="disabled")
        self.clear_button.config(state="disabled")

        self.progress.start(12)

    def enable_controls(self):

        self.open_button.config(state="normal")
        self.redact_button.config(state="normal")
        self.clear_button.config(state="normal")

        self.progress.stop()

    #################################################################
    # Redaction
    #################################################################

    def start_redaction(self):

        source_text = self.input_text.get(
            "1.0",
            tk.END
        ).strip()

        if not source_text:

            messagebox.showwarning(
                "No Input",
                "Please enter or load text."
            )

            return

        self.disable_controls()

        worker = threading.Thread(
            target=self.redaction_worker,
            args=(source_text,),
            daemon=True
        )

        worker.start()

    def redaction_worker(self, text):

        try:

            self.initialize_model()

            self.root.after(
                0,
                lambda: self.set_status(
                    f"Redacting ({self.device.upper()})..."
                )
            )

            result = self.opf.redact(text)

            redacted = getattr(
                result,
                "redacted_text",
                str(result)
            )

            self.root.after(
                0,
                lambda: self.show_result(redacted)
            )

        except Exception:

            import traceback

            traceback.print_exc()

            error_text = traceback.format_exc()

            self.root.after(
                0,
                lambda: messagebox.showerror(
                    "OPF Error",
                    error_text
                )
            )

        finally:

            self.root.after(
                0,
                self.enable_controls
            )

    def show_result(self, text):

        self.output_text.delete(
            "1.0",
            tk.END
        )

        self.output_text.insert(
            "1.0",
            text
        )

        self.set_status(
            f"Redaction complete ({self.device.upper()})"
        )

    #################################################################
    # Utility Buttons
    #################################################################

    def clear_all(self):

        self.input_text.delete(
            "1.0",
            tk.END
        )

        self.output_text.delete(
            "1.0",
            tk.END
        )

        self.set_status("Cleared")

    def copy_output(self):

        text = self.output_text.get(
            "1.0",
            tk.END
        )

        self.root.clipboard_clear()
        self.root.clipboard_append(text)

        self.set_status(
            "Output copied to clipboard"
        )

    def save_output(self):

        filename = filedialog.asksaveasfilename(
            initialdir=self.last_directory,
            defaultextension=".txt",
            filetypes=[
                ("Text Files", "*.txt"),
                ("All Files", "*.*")
            ]
        )

        if not filename:
            return

        self.last_directory = os.path.dirname(
            filename
        )

        try:

            text = self.output_text.get(
                "1.0",
                tk.END
            )

            with open(
                filename,
                "w",
                encoding="utf-8"
            ) as f:

                f.write(text)

            self.set_status(
                f"Saved {os.path.basename(filename)}"
            )

        except Exception as ex:

            messagebox.showerror(
                "Save Error",
                str(ex)
            )


def main():

    root = TkinterDnD.Tk()

    try:
        root.tk.call(
            "tk",
            "scaling",
            1.25
        )
    except Exception:
        pass

    OPFGui(root)

    root.mainloop()


if __name__ == "__main__":
    main()
