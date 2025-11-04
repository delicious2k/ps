"""Text Diff and Merge Tool.

This application compares two text documents, highlights their differences,
and helps users create a merged result. It is implemented with only the
Python standard library so it can run on Windows and macOS without extra
dependencies.
"""

import difflib
from bisect import bisect_left
import tkinter as tk
from tkinter import filedialog, messagebox
from typing import Any, Dict, List, Optional, Tuple


class DiffBlock:
    """Container describing a single difference block."""

    def __init__(
        self,
        tag: str,
        left_range: Tuple[int, int],
        right_range: Tuple[int, int],
        left_tag: Optional[str] = None,
        right_tag: Optional[str] = None,
    ) -> None:
        self.tag = tag
        self.left_range = left_range
        self.right_range = right_range
        self.left_tag = left_tag
        self.right_tag = right_tag


class DiffMergeApp:
    """GUI application for comparing and merging text files."""

    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Text Diff and Merge Tool")
        self.root.geometry("1200x700")

        self.left_diff_tags: List[str] = []
        self.right_diff_tags: List[str] = []
        self.blocks: List[DiffBlock] = []
        self.current_block_index: Optional[int] = None
        self._sync_in_progress = False
        self.line_number_canvases: Dict[tk.Text, tk.Canvas] = {}
        self._opcodes: List[Tuple[str, int, int, int, int]] = []
        self._spacers_applied = False

        self._build_ui()

    # ------------------------------------------------------------------ UI --
    def _build_ui(self) -> None:
        button_bar = tk.Frame(self.root)
        button_bar.pack(side=tk.TOP, fill=tk.X, padx=6, pady=6)

        tk.Button(button_bar, text="Load Left", command=self.load_left).pack(
            side=tk.LEFT, padx=2
        )
        tk.Button(button_bar, text="Load Right", command=self.load_right).pack(
            side=tk.LEFT, padx=2
        )
        tk.Button(button_bar, text="Compare", command=self.compare_texts).pack(
            side=tk.LEFT, padx=10
        )
        self.sync_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            button_bar,
            text="Sync View",
            variable=self.sync_var,
            command=self.toggle_sync_view,
        ).pack(side=tk.LEFT, padx=2)
        tk.Button(button_bar, text="Previous Difference", command=self.prev_block).pack(
            side=tk.LEFT, padx=2
        )
        tk.Button(button_bar, text="Next Difference", command=self.next_block).pack(
            side=tk.LEFT, padx=2
        )
        tk.Button(button_bar, text="Use Left", command=self.merge_left).pack(
            side=tk.LEFT, padx=10
        )
        tk.Button(button_bar, text="Use Right", command=self.merge_right).pack(
            side=tk.LEFT, padx=2
        )
        tk.Button(button_bar, text="Copy Both", command=self.merge_both).pack(
            side=tk.LEFT, padx=2
        )
        tk.Button(button_bar, text="Clear Merge", command=self.clear_merge).pack(
            side=tk.LEFT, padx=10
        )
        tk.Button(button_bar, text="Save Merge", command=self.save_merge).pack(
            side=tk.LEFT, padx=2
        )

        self.status_var = tk.StringVar()
        self.status_var.set("Load two files or paste text, then click Compare.")
        status_bar = tk.Label(self.root, textvariable=self.status_var, anchor="w")
        status_bar.pack(side=tk.BOTTOM, fill=tk.X, padx=6, pady=(0, 6))

        panes = tk.PanedWindow(self.root, orient=tk.HORIZONTAL, sashrelief=tk.RAISED)
        panes.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        left_frame = self._build_text_panel(panes, "Left Document")
        right_frame = self._build_text_panel(panes, "Right Document")
        merge_frame = self._build_text_panel(panes, "Merged Result")

        panes.add(left_frame, minsize=200, stretch="always")
        panes.add(right_frame, minsize=200, stretch="always")
        panes.add(merge_frame, minsize=200, stretch="always")

        self.left_text = self._text_widget_from_frame(left_frame)
        self.right_text = self._text_widget_from_frame(right_frame)
        self.merge_text = self._text_widget_from_frame(merge_frame)

        self.left_y_scroll = left_frame.y_scroll  # type: ignore[attr-defined]
        self.right_y_scroll = right_frame.y_scroll  # type: ignore[attr-defined]

        for widget in (self.left_text, self.right_text):
            widget.tag_configure("spacer")

        self.left_text.configure(
            yscrollcommand=lambda first, last: self._on_text_scroll(
                self.left_text, self.left_y_scroll, first, last
            )
        )
        self.right_text.configure(
            yscrollcommand=lambda first, last: self._on_text_scroll(
                self.right_text, self.right_y_scroll, first, last
            )
        )

        self.left_text.bind("<MouseWheel>", self._on_mousewheel, add=True)
        self.right_text.bind("<MouseWheel>", self._on_mousewheel, add=True)
        self.left_text.bind("<Button-4>", self._on_mousewheel, add=True)
        self.left_text.bind("<Button-5>", self._on_mousewheel, add=True)
        self.right_text.bind("<Button-4>", self._on_mousewheel, add=True)
        self.right_text.bind("<Button-5>", self._on_mousewheel, add=True)

        self.left_text.tag_configure("delete", background="#ffecec")
        self.right_text.tag_configure("insert", background="#e8f4ff")
        for widget in (self.left_text, self.right_text):
            widget.tag_configure("replace", background="#fff4e5")
            widget.tag_configure(
                "current",
                background="#ffe066",
                borderwidth=2,
                relief="solid",
            )

        self._setup_drag_and_drop()

    def _build_text_panel(self, parent: tk.PanedWindow, title: str) -> tk.Frame:
        frame = tk.Frame(parent)
        label = tk.Label(frame, text=title)
        label.pack(side=tk.TOP, anchor="w")

        container = tk.Frame(frame)
        container.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        line_numbers = tk.Canvas(
            container,
            width=50,
            highlightthickness=0,
            background="#f7f7f7",
        )
        text = tk.Text(container, wrap=tk.NONE, undo=True)
        y_scroll = tk.Scrollbar(container, orient=tk.VERTICAL, command=text.yview)
        x_scroll = tk.Scrollbar(container, orient=tk.HORIZONTAL, command=text.xview)
        text.configure(xscrollcommand=x_scroll.set)

        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(1, weight=1)

        line_numbers.grid(row=0, column=0, sticky="ns")
        text.grid(row=0, column=1, sticky="nsew")
        y_scroll.grid(row=0, column=2, sticky="ns")
        x_scroll.grid(row=1, column=1, sticky="ew")

        frame.text_widget = text  # type: ignore[attr-defined]
        frame.y_scroll = y_scroll  # type: ignore[attr-defined]
        frame.line_numbers = line_numbers  # type: ignore[attr-defined]

        self._register_line_numbers(text, line_numbers)
        self.root.after_idle(lambda widget=text: self._update_line_numbers(widget))

        return frame

    @staticmethod
    def _text_widget_from_frame(frame: tk.Frame) -> tk.Text:
        return frame.text_widget  # type: ignore[attr-defined]

    def _register_line_numbers(self, widget: tk.Text, canvas: tk.Canvas) -> None:
        self.line_number_canvases[widget] = canvas
        widget.bind(
            "<<Modified>>",
            lambda event, widget=widget: self._on_text_modified(widget),
            add=True,
        )
        widget.bind(
            "<Configure>",
            lambda event, widget=widget: self._update_line_numbers(widget),
            add=True,
        )
        try:
            widget.edit_modified(False)
        except tk.TclError:
            pass

    def _on_text_modified(self, widget: tk.Text) -> None:
        try:
            widget.edit_modified(False)
        except tk.TclError:
            pass
        self._update_line_numbers(widget)

    def _update_line_numbers(self, widget: tk.Text) -> None:
        canvas = self.line_number_canvases.get(widget)
        if not canvas:
            return
        canvas.delete("all")

        total_lines = self._line_count(widget)
        spacer_lines = self._spacer_line_numbers(widget)
        visible_lines = max(total_lines - len(spacer_lines), 1)
        digits = max(2, len(str(visible_lines)))
        pixel_width = digits * 8 + 12
        if canvas.winfo_width() != pixel_width:
            canvas.config(width=pixel_width)

        index = widget.index("@0,0")
        font = widget.cget("font")
        spacer_set = set(spacer_lines)
        while True:
            dline = widget.dlineinfo(index)
            if dline is None:
                break
            y = dline[1]
            line_number_str = index.split(".")[0]
            line_number = int(line_number_str)
            next_index = widget.index(f"{line_number}.0 +1line")
            if line_number in spacer_set:
                index = next_index
                continue
            adjusted_number = line_number - bisect_left(spacer_lines, line_number)
            canvas.create_text(
                pixel_width - 6,
                y,
                anchor="ne",
                text=str(max(adjusted_number, 1)),
                font=font,
                fill="#555555",
            )
            index = next_index

    def _spacer_line_numbers(self, widget: tk.Text) -> List[int]:
        ranges = widget.tag_ranges("spacer")
        if not ranges:
            return []
        lines: List[int] = []
        for start, end in zip(ranges[::2], ranges[1::2]):
            current = widget.index(start)
            while widget.compare(current, "<", end):
                line_number = int(current.split(".")[0])
                lines.append(line_number)
                current = widget.index(f"{line_number}.0 +1line")
        lines.sort()
        return lines

    # -------------------------------------------------------- Drag & Drop --
    def _setup_drag_and_drop(self) -> None:
        try:
            self.root.tk.eval("package require tkdnd")
        except tk.TclError:
            base_message = self.status_var.get()
            self.status_var.set(
                f"{base_message}\nDrag and drop not available (tkdnd package missing)."
            )
            return

        for widget, side in (
            (self.left_text, "left"),
            (self.right_text, "right"),
        ):
            try:
                widget.drop_target_register("DND_Files")
                widget.dnd_bind(
                    "<<Drop>>",
                    lambda event, side=side, widget=widget: self._on_drop(event, widget, side),
                )
            except tk.TclError:
                # If binding fails on one widget, continue without drag-and-drop.
                continue

    def _on_drop(self, event: Any, widget: tk.Text, side: str) -> None:
        paths = self.root.tk.splitlist(event.data)
        if not paths:
            return
        path = paths[0]
        if path.startswith("{") and path.endswith("}"):
            path = path[1:-1]
        self._load_file_into_widget(path, widget, side)

    # --------------------------------------------------- Spacer handling --
    def _remove_spacer_lines(self) -> None:
        for widget in (self.left_text, self.right_text):
            ranges = list(widget.tag_ranges("spacer"))
            if not ranges:
                continue
            for start, end in reversed(list(zip(ranges[::2], ranges[1::2]))):
                widget.delete(start, end)
            widget.tag_remove("spacer", "1.0", tk.END)
            self._update_line_numbers(widget)
        self._spacers_applied = False

    def _apply_alignment_spacers(self) -> None:
        if self._spacers_applied:
            return
        if not self._opcodes:
            self._spacers_applied = True
            return
        self._remove_spacer_lines()
        left_offset = 0
        right_offset = 0
        inserted = False
        for tag, i1, i2, j1, j2 in self._opcodes:
            if tag == "equal":
                continue
            left_len = i2 - i1
            right_len = j2 - j1
            if left_len == right_len:
                continue
            if left_len > right_len:
                count = left_len - right_len
                line = j2 + right_offset + 1
                self._insert_spacer_lines(self.right_text, line, count)
                right_offset += count
            else:
                count = right_len - left_len
                line = i2 + left_offset + 1
                self._insert_spacer_lines(self.left_text, line, count)
                left_offset += count
            inserted = True
        if inserted:
            for widget in (self.left_text, self.right_text):
                self._update_line_numbers(widget)
        self._spacers_applied = True

    def _insert_spacer_lines(self, widget: tk.Text, line: int, count: int) -> None:
        if count <= 0:
            return
        index = widget.index(f"{line}.0")
        widget.insert(index, "\n" * count)
        self._tag_spacer_lines(widget, line, count)

    def _tag_spacer_lines(self, widget: tk.Text, start_line: int, count: int) -> None:
        for offset in range(count):
            line_number = start_line + offset
            start_index = widget.index(f"{line_number}.0")
            end_index = widget.index(f"{line_number}.0 +1line")
            widget.tag_add("spacer", start_index, end_index)

    def _is_spacer_line(self, widget: tk.Text, line: int) -> bool:
        start_index = widget.index(f"{line}.0")
        end_index = widget.index(f"{line}.0 +1line")
        return bool(widget.tag_nextrange("spacer", start_index, end_index))

    # ----------------------------------------------------- Sync Handling --
    def toggle_sync_view(self) -> None:
        if not self.sync_var.get():
            self._remove_spacer_lines()
            self.update_status("Sync view disabled.")
            return
        self._apply_alignment_spacers()
        focus_widget = self.root.focus_get()
        if focus_widget not in (self.left_text, self.right_text):
            focus_widget = self.left_text
        self._align_partner_scroll(focus_widget)  # type: ignore[arg-type]
        self.update_status("Sync view enabled. Scrolls are now linked.")

    def _on_text_scroll(
        self, widget: tk.Text, scrollbar: tk.Scrollbar, first: str, last: str
    ) -> None:
        scrollbar.set(first, last)
        self._update_line_numbers(widget)
        if not self.sync_var.get() or self._sync_in_progress:
            return
        partner = self.right_text if widget is self.left_text else self.left_text
        line = self._first_visible_line(widget)
        self._sync_in_progress = True
        self._move_to_line(partner, line)
        self._sync_in_progress = False
        self._update_line_numbers(partner)

    def _align_partner_scroll(self, widget: tk.Text) -> None:
        partner = self.right_text if widget is self.left_text else self.left_text
        line = self._first_visible_line(widget)
        self._sync_in_progress = True
        self._move_to_line(partner, line)
        self._sync_in_progress = False
        self._update_line_numbers(widget)
        self._update_line_numbers(partner)

    def _first_visible_line(self, widget: tk.Text) -> int:
        try:
            index = widget.index("@0,0")
            return max(int(index.split(".")[0]), 1)
        except (ValueError, tk.TclError):
            return 1

    def _move_to_line(self, widget: tk.Text, line: int) -> None:
        total_lines = self._line_count(widget)
        if total_lines <= 1:
            widget.yview_moveto(0.0)
            self._update_line_numbers(widget)
            return
        target_line = min(max(line, 1), total_lines)
        index = f"{target_line}.0"
        try:
            widget.see(index)
            widget.update_idletasks()
            pixels_from_start = widget.count("1.0", index, "ypixels")
            total_pixels = widget.count("1.0", "end", "ypixels")
            if (
                pixels_from_start
                and total_pixels
                and pixels_from_start[0] is not None
                and total_pixels[0]
            ):
                widget.yview_moveto(pixels_from_start[0] / total_pixels[0])
            else:
                raise tk.TclError
        except tk.TclError:
            fraction = (target_line - 1) / max(total_lines - 1, 1)
            widget.yview_moveto(fraction)
        self._update_line_numbers(widget)

    def _line_count(self, widget: tk.Text) -> int:
        try:
            return max(int(widget.index("end-1c").split(".")[0]), 1)
        except (ValueError, tk.TclError):
            return 1

    def _on_mousewheel(self, event: Any) -> str:
        widget = event.widget
        if not isinstance(widget, tk.Text):
            return "break"
        if getattr(event, "delta", 0):
            delta = event.delta
            if abs(delta) < 120:
                step = -1 if delta > 0 else 1
            else:
                step = int(-delta / 120)
            widget.yview_scroll(step, "units")
        elif getattr(event, "num", None) == 4:
            widget.yview_scroll(-1, "units")
        elif getattr(event, "num", None) == 5:
            widget.yview_scroll(1, "units")
        return "break"

    # -------------------------------------------------------------- Actions --
    def load_left(self) -> None:
        path = filedialog.askopenfilename(title="Open Left File")
        if path:
            self._load_file_into_widget(path, self.left_text, "left")

    def load_right(self) -> None:
        path = filedialog.askopenfilename(title="Open Right File")
        if path:
            self._load_file_into_widget(path, self.right_text, "right")

    def _load_file_into_widget(self, path: str, widget: tk.Text, side: str) -> None:
        self._remove_spacer_lines()
        self._opcodes = []
        try:
            with open(path, "r", encoding="utf-8") as file:
                contents = file.read()
        except OSError as exc:
            messagebox.showerror("Error", f"Could not open file:\n{exc}")
            return
        widget.delete("1.0", tk.END)
        widget.insert("1.0", contents)
        self._update_line_numbers(widget)
        self.update_status(f"Loaded {side} file: {path}")

    def compare_texts(self) -> None:
        self._remove_spacer_lines()
        left_lines = self.left_text.get("1.0", tk.END).splitlines()
        right_lines = self.right_text.get("1.0", tk.END).splitlines()

        self._clear_highlights()
        self.blocks.clear()
        self.current_block_index = None
        self._opcodes = []

        matcher = difflib.SequenceMatcher(None, left_lines, right_lines)
        self._opcodes = list(matcher.get_opcodes())
        for index, (tag, i1, i2, j1, j2) in enumerate(self._opcodes):
            if tag == "equal":
                continue

            left_tag = None
            right_tag = None
            if i2 > i1:
                left_tag = f"left_block_{index}"
                self._highlight_block(
                    self.left_text,
                    left_tag,
                    tag if tag in {"replace"} else "delete",
                    i1,
                    i2,
                )
            if j2 > j1:
                right_tag = f"right_block_{index}"
                self._highlight_block(
                    self.right_text,
                    right_tag,
                    tag if tag in {"replace"} else "insert",
                    j1,
                    j2,
                )
            self.blocks.append(
                DiffBlock(tag, (i1, i2), (j1, j2), left_tag=left_tag, right_tag=right_tag)
            )

        if not self.blocks:
            self.update_status("The documents are identical.")
            return

        if self.sync_var.get():
            self._apply_alignment_spacers()
        else:
            self._spacers_applied = False

        self.update_status(f"Found {len(self.blocks)} differing block(s).")
        self.current_block_index = 0
        self._apply_current_block()

    def _highlight_block(
        self, widget: tk.Text, tag_name: str, style_tag: str, start: int, end: int
    ) -> None:
        widget.tag_delete(tag_name)
        widget.tag_configure(tag_name, background=widget.tag_cget(style_tag, "background"))
        start_index = f"{start + 1}.0"
        end_index = f"{end}.0"
        if start == end:
            return
        if end_index == "0.0":
            end_index = tk.END
        else:
            end_index = widget.index(f"{end}.0 lineend +1c")
        widget.tag_add(tag_name, start_index, end_index)
        if widget is self.left_text:
            self.left_diff_tags.append(tag_name)
        else:
            self.right_diff_tags.append(tag_name)

    def prev_block(self) -> None:
        if not self.blocks:
            return
        if self.current_block_index is None:
            self.current_block_index = 0
        else:
            self.current_block_index = (self.current_block_index - 1) % len(self.blocks)
        self._apply_current_block()

    def next_block(self) -> None:
        if not self.blocks:
            return
        if self.current_block_index is None:
            self.current_block_index = 0
        else:
            self.current_block_index = (self.current_block_index + 1) % len(self.blocks)
        self._apply_current_block()

    def _apply_current_block(self) -> None:
        if self.current_block_index is None or not self.blocks:
            return
        block = self.blocks[self.current_block_index]
        for widget in (self.left_text, self.right_text):
            widget.tag_remove("current", "1.0", tk.END)

        if block.left_tag:
            self._apply_current_tag(self.left_text, block.left_range)
        if block.right_tag:
            self._apply_current_tag(self.right_text, block.right_range)

        self.update_status(
            f"Viewing difference {self.current_block_index + 1} of {len(self.blocks)}"
        )

    def _apply_current_tag(self, widget: tk.Text, text_range: Tuple[int, int]) -> None:
        start, end = text_range
        if start == end:
            return
        start_index = f"{start + 1}.0"
        end_index = widget.index(f"{end}.0 lineend +1c")
        widget.tag_add("current", start_index, end_index)
        widget.tag_raise("current")
        widget.see(start_index)

    def merge_left(self) -> None:
        self._merge_choice(prefer="left")

    def merge_right(self) -> None:
        self._merge_choice(prefer="right")

    def merge_both(self) -> None:
        self._merge_choice(prefer="both")

    def _merge_choice(self, prefer: str) -> None:
        if self.current_block_index is None:
            messagebox.showinfo("Merge", "No difference selected.")
            return
        block = self.blocks[self.current_block_index]
        left_text = self._extract_range(self.left_text, block.left_range)
        right_text = self._extract_range(self.right_text, block.right_range)

        if prefer == "left":
            chosen = left_text
        elif prefer == "right":
            chosen = right_text
        else:  # both
            chosen = left_text + right_text

        if not chosen:
            messagebox.showinfo("Merge", "Nothing to merge for this choice.")
            return

        if not self.merge_text.get("1.0", tk.END).strip():
            insert_point = "1.0"
        else:
            insert_point = tk.END
        self.merge_text.insert(insert_point, chosen)
        self._update_line_numbers(self.merge_text)
        self.update_status("Appended selection to the merged document.")

    def clear_merge(self) -> None:
        self.merge_text.delete("1.0", tk.END)
        self._update_line_numbers(self.merge_text)
        self.update_status("Cleared merged document.")

    def save_merge(self) -> None:
        contents = self.merge_text.get("1.0", tk.END)
        if not contents.strip():
            messagebox.showinfo("Save", "Merged document is empty.")
            return
        path = filedialog.asksaveasfilename(title="Save Merged File")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as file:
                file.write(contents)
        except OSError as exc:
            messagebox.showerror("Error", f"Could not save file:\n{exc}")
            return
        self.update_status(f"Merged file saved to: {path}")

    def _extract_range(self, widget: tk.Text, text_range: Tuple[int, int]) -> str:
        start, end = text_range
        if start == end:
            return ""
        pieces: List[str] = []
        for line in range(start + 1, end + 1):
            if self._is_spacer_line(widget, line):
                continue
            line_start = widget.index(f"{line}.0")
            line_end = widget.index(f"{line}.0 +1line")
            pieces.append(widget.get(line_start, line_end))
        return "".join(pieces)

    def _clear_highlights(self) -> None:
        for tag in self.left_diff_tags:
            self.left_text.tag_delete(tag)
        for tag in self.right_diff_tags:
            self.right_text.tag_delete(tag)
        self.left_diff_tags.clear()
        self.right_diff_tags.clear()
        for widget in (self.left_text, self.right_text):
            widget.tag_remove("current", "1.0", tk.END)

    def update_status(self, message: str) -> None:
        self.status_var.set(message)

    def run(self) -> None:
        self.root.mainloop()


def main() -> None:
    app = DiffMergeApp()
    app.run()


if __name__ == "__main__":
    main()
