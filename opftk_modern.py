import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

#
# Dependency checks
#
try:
    import customtkinter as ctk
except ImportError:
    raise SystemExit(
        "Missing dependency: customtkinter\n\n"
        "Install with:\n"
        "pip install customtkinter"
    )

try:
    from PIL import Image, ImageDraw
except ImportError:
    raise SystemExit(
        "Missing dependency: image\n\n"
        "Install with:\n"
        "pip install image"
    )

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

        toolbar = ctk.CTkFrame(self.root)
        toolbar.pack(fill="x", padx=5, pady=5)

        # light border color so button/status fills sit inside a visible border
        border_color = ("gray93", "gray30")

        self.open_button = ctk.CTkButton(
            toolbar,
            text="Open File",
            image=self.icon("open"),
            anchor="w",
            border_width=1,
            border_color=border_color,
            command=self.open_file
        )
        self.open_button.pack(side="left", padx=2)

        self.redact_button = ctk.CTkButton(
            toolbar,
            text="Redact",
            image=self.icon("redact"),
            anchor="w",
            border_width=1,
            border_color=border_color,
            command=self.start_redaction
        )
        self.redact_button.pack(side="left", padx=2)

        self.clear_button = ctk.CTkButton(
            toolbar,
            text="Clear",
            image=self.icon("clear"),
            anchor="w",
            border_width=1,
            border_color=border_color,
            command=self.clear_all
        )
        self.clear_button.pack(side="left", padx=2)

        self.copy_button = ctk.CTkButton(
            toolbar,
            text="Copy Output",
            image=self.icon("copy"),
            anchor="w",
            border_width=1,
            border_color=border_color,
            command=self.copy_output
        )
        self.copy_button.pack(side="left", padx=2)

        self.save_button = ctk.CTkButton(
            toolbar,
            text="Save Output",
            image=self.icon("save"),
            anchor="w",
            border_width=1,
            border_color=border_color,
            command=self.save_output
        )
        self.save_button.pack(side="left", padx=2)

        self.about_button = ctk.CTkButton(
            toolbar,
            text="About",
            image=self.icon("about"),
            anchor="w",
            border_width=1,
            border_color=border_color,
            command=self.show_about
        )
        self.about_button.pack(side="left", padx=2)

        self.progress = ctk.CTkProgressBar(
            toolbar,
            width=200,
            mode="indeterminate"
        )
        self.progress.set(0)

        self.progress.pack(
            side="right",
            padx=10,
            pady=4
        )

        style = ttk.Style(self.root)
        style.theme_use("clam")

        try:
            if ctk.get_appearance_mode() == "Dark":
                sash_color = "#2f2f2f"
            else:
                sash_color = "#c8c8c8"
        except Exception:
            sash_color = "#a0a0a0"

        style.configure(
            "TPanedwindow.Sash",
            background=sash_color,
            sashthickness=4
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

        left_frame = ctk.CTkFrame(paned)
        right_frame = ctk.CTkFrame(paned)

        paned.add(left_frame, weight=1)
        paned.add(right_frame, weight=1)

        def _center_sash():
            width = paned.winfo_width()
            if width > 1:
                paned.sashpos(0, width // 2)
            else:
                self.root.after(50, _center_sash)

        self.root.after(150, _center_sash)

        ctk.CTkLabel(
            left_frame,
            text="Input Text"
        ).pack(anchor="w", padx=(10, 0))

        self.mono_font = ctk.CTkFont(
            family="Consolas",
            size=14
        )

        self.input_text = ctk.CTkTextbox(
            left_frame,
            wrap="word",
            undo=True,
            font=self.mono_font
        )

        self.input_text.pack(
            fill="both",
            expand=True,
            padx=10,
            pady=(0, 10)
        )

        ctk.CTkLabel(
            right_frame,
            text="Redacted Output"
        ).pack(anchor="w", padx=(10, 0))

        self.output_text = ctk.CTkTextbox(
            right_frame,
            wrap="word",
            font=self.mono_font
        )

        self.output_text.pack(
            fill="both",
            expand=True,
            padx=10,
            pady=(0, 10)
        )

        self.status_var = tk.StringVar()
        self.status_var.set("Ready")

        self._check_icon = self.icon(
            "check",
            color=(34, 197, 94, 255)
        )

        self._empty_icon = ctk.CTkImage(
            light_image=Image.new("RGBA", (1, 1), (0, 0, 0, 0)),
            dark_image=Image.new("RGBA", (1, 1), (0, 0, 0, 0)),
            size=(1, 1)
        )

        status_frame = ctk.CTkFrame(
            self.root,
            fg_color=("gray85", "gray25"),
            border_width=1,
            border_color=border_color,
            corner_radius=6
        )

        status_frame.pack(
            fill="x",
            side="bottom"
        )

        status_frame.grid_columnconfigure(1, weight=1)

        self.status_icon = ctk.CTkLabel(
            status_frame,
            fg_color="transparent",
            text=""
        )

        self.status_icon.grid(
            row=0,
            column=0,
            sticky="w",
            padx=(10, 6),
            pady=8
        )

        self.status_label = ctk.CTkLabel(
            status_frame,
            textvariable=self.status_var,
            anchor="w",
            fg_color="transparent",
            text_color=("gray10", "gray95")
        )

        self.status_label.grid(
            row=0,
            column=1,
            sticky="we",
            padx=(0, 12),
            pady=8
        )

        self.input_text.drop_target_register(DND_FILES)

        self.input_text.dnd_bind(
            "<<Drop>>",
            self.on_drop
        )

    #################################################################
    # Button / Status Icons
    #################################################################

    def icon(self, kind, size=20, color=None):

        try:

            if color is not None:
                light_img = self._render_icon(kind, size, color)
                dark_img = self._render_icon(kind, size, color)
            else:
                light_img = self._render_icon(
                    kind, size, (35, 35, 35, 255)
                )
                dark_img = self._render_icon(
                    kind, size, (228, 228, 228, 255)
                )

            return ctk.CTkImage(
                light_image=light_img,
                dark_image=dark_img,
                size=(size, size)
            )

        except Exception:

            import traceback
            traceback.print_exc()
            return None

    def _render_icon(self, kind, size, color):

        supersample = 8
        S = size * supersample
        u = S / 100.0

        img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)

        w = int(round(size * 0.13 * supersample))
        if w < 2:
            w = 2

        def box(rect):
            return [rect[0] * u, rect[1] * u, rect[2] * u, rect[3] * u]

        def pt(p):
            return (p[0] * u, p[1] * u)

        if kind == "open":

            d.rounded_rectangle(
                box([8, 30, 42, 48]),
                radius=int(6 * u),
                outline=color,
                width=w
            )
            d.rounded_rectangle(
                box([8, 40, 92, 92]),
                radius=int(8 * u),
                outline=color,
                width=w
            )

        elif kind == "redact":

            d.rounded_rectangle(
                box([30, 10, 70, 92]),
                radius=int(6 * u),
                outline=color,
                width=w
            )
            d.line([pt([42, 32]), pt([58, 32])], fill=color, width=w)
            d.rounded_rectangle(
                box([40, 50, 60, 66]),
                radius=int(3 * u),
                fill=color
            )
            d.line([pt([42, 80]), pt([58, 80])], fill=color, width=w)

        elif kind == "clear":

            d.line([pt([30, 34]), pt([70, 34])], fill=color, width=w)
            d.line([pt([44, 34]), pt([44, 24])], fill=color, width=w)
            d.line([pt([56, 34]), pt([56, 24])], fill=color, width=w)
            d.line([pt([44, 24]), pt([56, 24])], fill=color, width=w)
            d.polygon(
                [pt([34, 34]), pt([66, 34]), pt([60, 88]), pt([40, 88])],
                outline=color,
                width=w
            )
            d.line(
                [pt([46, 48]), pt([44, 78])],
                fill=color,
                width=max(2, int(w * 0.7))
            )
            d.line(
                [pt([54, 48]), pt([56, 78])],
                fill=color,
                width=max(2, int(w * 0.7))
            )

        elif kind == "copy":

            d.rounded_rectangle(
                box([16, 16, 64, 64]),
                radius=int(8 * u),
                outline=color,
                width=w
            )
            d.rounded_rectangle(
                box([36, 36, 84, 84]),
                radius=int(8 * u),
                outline=color,
                width=w
            )

        elif kind == "save":

            d.line([pt([50, 18]), pt([50, 66])], fill=color, width=w)
            d.polygon(
                [pt([34, 52]), pt([50, 70]), pt([66, 52])],
                outline=color,
                width=w
            )
            d.line([pt([24, 80]), pt([24, 90])], fill=color, width=w)
            d.line([pt([24, 90]), pt([76, 90])], fill=color, width=w)
            d.line([pt([76, 80]), pt([76, 90])], fill=color, width=w)

        elif kind == "about":

            d.ellipse(box([22, 22, 78, 78]), outline=color, width=w)
            d.ellipse(box([45, 34, 55, 44]), fill=color)
            d.line([pt([50, 52]), pt([50, 70])], fill=color, width=w)

        elif kind == "check":

            d.ellipse(box([18, 18, 82, 82]), outline=color, width=w)
            d.line([pt([34, 52]), pt([46, 64])], fill=color, width=w)
            d.line([pt([46, 64]), pt([68, 40])], fill=color, width=w)

        else:
            return None

        return img.resize((size, size), Image.LANCZOS)

    #################################################################
    # Status
    #################################################################

    def set_status(self, text, check=False):

        self.status_var.set(text)

        if check:
            self.status_icon.configure(
                image=self._check_icon
            )
        else:
            self.status_icon.configure(
                image=self._empty_icon
            )

    #################################################################
    # About
    #################################################################

    def show_about(self):

        messagebox.showinfo(
            "About",
            "Open Privacy Filter GUI\n\n"
            "- Desktop GUI front-end for OPF\n"
            "- Supports drag-and-drop text files\n"
            "- Automatically selects GPU or CPU\n"
            "- Windows, macOS, and Linux compatible\n"
            "- Version: 0.0.4\n"
            "- License: Apache 2.0\n"
            "- Website: https://github.com/uwsph/opftk"
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

        self.open_button.configure(state="disabled")
        self.redact_button.configure(state="disabled")
        self.clear_button.configure(state="disabled")

        self.progress.start()

    def enable_controls(self):

        self.open_button.configure(state="normal")
        self.redact_button.configure(state="normal")
        self.clear_button.configure(state="normal")

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
            f"Redaction complete ({self.device.upper()})",
            check=True
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

    ctk.set_appearance_mode("System")
    ctk.set_default_color_theme("blue")

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
