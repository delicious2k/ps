"""Text Diff and Merge Tool.

This application compares two text documents, highlights their differences,
and helps users create a merged result. It is implemented with only the
Python standard library so it can run on Windows and macOS without extra
dependencies.
"""

import difflib
import tkinter as tk
from tkinter import filedialog, messagebox
from typing import List, Optional, Tuple


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

        panes = tk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        panes.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        left_frame = self._build_text_panel(panes, "Left Document")
        right_frame = self._build_text_panel(panes, "Right Document")
        merge_frame = self._build_text_panel(panes, "Merged Result")

        panes.add(left_frame)
        panes.add(right_frame)
        panes.add(merge_frame)

        self.left_text = self._text_widget_from_frame(left_frame)
        self.right_text = self._text_widget_from_frame(right_frame)
        self.merge_text = self._text_widget_from_frame(merge_frame)

        self.left_text.tag_configure("delete", background="#ffecec")
        self.right_text.tag_configure("insert", background="#e8f4ff")
        for widget in (self.left_text, self.right_text):
            widget.tag_configure("replace", background="#fff4e5")
            widget.tag_configure("current", background="#fff2a8")

    def _build_text_panel(self, parent: tk.PanedWindow, title: str) -> tk.Frame:
        frame = tk.Frame(parent)
        label = tk.Label(frame, text=title)
        label.pack(side=tk.TOP, anchor="w")

        text = tk.Text(frame, wrap=tk.NONE, undo=True)
        y_scroll = tk.Scrollbar(frame, command=text.yview)
        x_scroll = tk.Scrollbar(frame, orient=tk.HORIZONTAL, command=text.xview)
        text.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)

        text.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        x_scroll.pack(side=tk.BOTTOM, fill=tk.X)

        frame.text_widget = text  # type: ignore[attr-defined]
        return frame

    @staticmethod
    def _text_widget_from_frame(frame: tk.Frame) -> tk.Text:
        return frame.text_widget  # type: ignore[attr-defined]

    # -------------------------------------------------------------- Actions --
    def load_left(self) -> None:
        path = filedialog.askopenfilename(title="Open Left File")
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as file:
                contents = file.read()
        except OSError as exc:
            messagebox.showerror("Error", f"Could not open file:\n{exc}")
            return
        self.left_text.delete("1.0", tk.END)
        self.left_text.insert("1.0", contents)
        self.update_status(f"Loaded left file: {path}")

    def load_right(self) -> None:
        path = filedialog.askopenfilename(title="Open Right File")
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as file:
                contents = file.read()
        except OSError as exc:
            messagebox.showerror("Error", f"Could not open file:\n{exc}")
            return
        self.right_text.delete("1.0", tk.END)
        self.right_text.insert("1.0", contents)
        self.update_status(f"Loaded right file: {path}")

    def compare_texts(self) -> None:
        left_lines = self.left_text.get("1.0", tk.END).splitlines()
        right_lines = self.right_text.get("1.0", tk.END).splitlines()

        self._clear_highlights()
        self.blocks.clear()
        self.current_block_index = None

        matcher = difflib.SequenceMatcher(None, left_lines, right_lines)
        for index, (tag, i1, i2, j1, j2) in enumerate(matcher.get_opcodes()):
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
        self.update_status("Appended selection to the merged document.")

    def clear_merge(self) -> None:
        self.merge_text.delete("1.0", tk.END)
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
        start_index = f"{start + 1}.0"
        end_index = widget.index(f"{end}.0 lineend +1c")
        return widget.get(start_index, end_index)

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
