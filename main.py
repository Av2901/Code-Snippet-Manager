import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from pygments import highlight
from pygments.lexers import guess_lexer, get_lexer_by_name, get_all_lexers
from pygments.formatters import HtmlFormatter
import pyperclip
import json
import webbrowser
from datetime import datetime
import os

class SnippetManager:
    def __init__(self):
        self.preview_after_id = None  # For delayed preview update
        self.setup_database()
        self.setup_ui()
        self.load_snippets()
        
    def setup_database(self):
        db_exists = os.path.exists("snippets.db")
        self.conn = sqlite3.connect("snippets.db")
        self.cursor = self.conn.cursor()
        
        if not db_exists:
            self.cursor.execute("""
                CREATE TABLE snippets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    code TEXT NOT NULL,
                    language TEXT NOT NULL,
                    tags TEXT NOT NULL,
                    description TEXT,
                    favorite INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_modified TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
        else:
            existing_columns = [row[1] for row in self.cursor.execute("PRAGMA table_info(snippets)")]
            if 'description' not in existing_columns:
                self.cursor.execute("ALTER TABLE snippets ADD COLUMN description TEXT")
            if 'created_at' not in existing_columns:
                current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                self.cursor.execute("ALTER TABLE snippets ADD COLUMN created_at TIMESTAMP")
                self.cursor.execute(f"UPDATE snippets SET created_at = '{current_time}'")
            if 'last_modified' not in existing_columns:
                current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                self.cursor.execute("ALTER TABLE snippets ADD COLUMN last_modified TIMESTAMP")
                self.cursor.execute(f"UPDATE snippets SET last_modified = '{current_time}'")
        self.conn.commit()

    def load_snippets(self):
        self.snippet_tree.delete(*self.snippet_tree.get_children())
        query = self.search_var.get().strip()
        self.cursor.execute("""
            SELECT 
                id, 
                title, 
                language, 
                tags, 
                COALESCE(last_modified, created_at, CURRENT_TIMESTAMP) as modified_date,
                favorite 
            FROM snippets 
            WHERE title LIKE ? OR tags LIKE ? OR language LIKE ?
            ORDER BY favorite DESC, modified_date DESC
        """, (f"%{query}%", f"%{query}%", f"%{query}%"))
        for row in self.cursor.fetchall():
            try:
                modified_date = datetime.strptime(row[4], '%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%d')
            except Exception:
                modified_date = "N/A"
            fav = "⭐" if row[5] else ""
            self.snippet_tree.insert("", tk.END, values=(row[0], row[1], row[2], row[3], modified_date, fav))

    def save_snippet(self):
        title = self.title_entry.get().strip()
        code = self.code_text.get("1.0", tk.END).strip()
        tags = self.tags_entry.get().strip()
        language = self.lang_combo.get() or self.guess_language(code)
        description = self.description_text.get("1.0", tk.END).strip()
        if not title or not code:
            messagebox.showwarning("Missing Data", "Title and Code are required!")
            return
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        selected = self.snippet_tree.selection()
        if selected:
            snippet_id = self.snippet_tree.item(selected)["values"][0]
            self.cursor.execute("""
                UPDATE snippets 
                SET title=?, code=?, language=?, tags=?, description=?, 
                    last_modified=?
                WHERE id=?
            """, (title, code, language, tags, description, current_time, snippet_id))
        else:
            self.cursor.execute("""
                INSERT INTO snippets (
                    title, code, language, tags, description, 
                    created_at, last_modified
                ) 
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (title, code, language, tags, description, current_time, current_time))
        self.conn.commit()
        self.log_activity("Snippet saved successfully!")
        self.load_snippets()

    def setup_ui(self):
        self.root = tb.Window(themename="darkly")
        self.root.title("Code Snippet Manager Pro")
        self.root.geometry("1400x900")
        self.setup_menubar()
        self.main_container = ttk.Frame(self.root, padding="10")
        self.main_container.pack(fill=tk.BOTH, expand=True)
        self.setup_topbar()
        self.content_frame = ttk.Frame(self.main_container)
        self.content_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        self.setup_left_pane()
        self.setup_right_pane()
        self.setup_statusbar()
        self.setup_shortcuts()
        self.search_timer = None

    def setup_menubar(self):
        menubar = tk.Menu(self.root)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Export Snippets", command=self.export_snippets)
        file_menu.add_command(label="Import Snippets", command=self.import_snippets)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        menubar.add_cascade(label="File", menu=file_menu)
        edit_menu = tk.Menu(menubar, tearoff=0)
        edit_menu.add_command(label="New Snippet", command=self.new_snippet, accelerator="Ctrl+N")
        edit_menu.add_command(label="Save Snippet", command=self.save_snippet, accelerator="Ctrl+S")
        edit_menu.add_command(label="Delete Snippet", command=self.delete_snippet, accelerator="Ctrl+D")
        edit_menu.add_command(label="Copy Code", command=self.copy_to_clipboard, accelerator="Ctrl+C")
        menubar.add_cascade(label="Edit", menu=edit_menu)
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="About", command=self.show_about)
        help_menu.add_command(label="Visit Website", command=lambda: webbrowser.open("https://www.example.com"))
        menubar.add_cascade(label="Help", menu=help_menu)
        self.root.config(menu=menubar)

    def setup_topbar(self):
        topbar = ttk.Frame(self.main_container)
        topbar.pack(fill=tk.X, pady=(0, 10))
        search_frame = ttk.Frame(topbar)
        search_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        search_label = ttk.Label(search_frame, text="🔍", font=("Arial", 12))
        search_label.pack(side=tk.LEFT, padx=(0, 5))
        self.search_var = tk.StringVar()
        self.search_var.trace("w", self.on_search_change)
        self.search_entry = ttk.Entry(search_frame, textvariable=self.search_var, font=("Arial", 11))
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        btn_frame = ttk.Frame(topbar)
        btn_frame.pack(side=tk.RIGHT)
        self.theme_btn = ttk.Button(btn_frame, text="🌓 Theme", command=self.toggle_theme, bootstyle=INFO)
        self.theme_btn.pack(side=tk.RIGHT, padx=5)
        self.fav_btn = ttk.Button(btn_frame, text="⭐ Toggle Favorite", command=self.toggle_favorite, bootstyle=WARNING)
        self.fav_btn.pack(side=tk.RIGHT, padx=5)
        self.settings_btn = ttk.Button(btn_frame, text="⚙️ Settings", command=self.show_settings, bootstyle=INFO)
        self.settings_btn.pack(side=tk.RIGHT, padx=5)

    def setup_left_pane(self):
        left_pane = ttk.Frame(self.content_frame)
        left_pane.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        list_toolbar = ttk.Frame(left_pane)
        list_toolbar.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(list_toolbar, text="Snippets", font=("Arial", 12, "bold")).pack(side=tk.LEFT)
        ttk.Button(list_toolbar, text="+ New", command=self.new_snippet, bootstyle=SUCCESS).pack(side=tk.RIGHT)
        columns = ("ID", "Title", "Language", "Tags", "Modified", "Favorite")
        self.snippet_tree = ttk.Treeview(left_pane, columns=columns, show="headings", selectmode="browse")
        self.snippet_tree.heading("ID", text="ID")
        self.snippet_tree.heading("Title", text="Title")
        self.snippet_tree.heading("Language", text="Language")
        self.snippet_tree.heading("Tags", text="Tags")
        self.snippet_tree.heading("Modified", text="Modified")
        self.snippet_tree.heading("Favorite", text="⭐")
        self.snippet_tree.column("ID", width=50, anchor=tk.CENTER)
        self.snippet_tree.column("Title", width=200)
        self.snippet_tree.column("Language", width=100)
        self.snippet_tree.column("Tags", width=150)
        self.snippet_tree.column("Modified", width=100)
        self.snippet_tree.column("Favorite", width=50, anchor=tk.CENTER)
        list_scroll = ttk.Scrollbar(left_pane, orient=tk.VERTICAL, command=self.snippet_tree.yview)
        self.snippet_tree.configure(yscrollcommand=list_scroll.set)
        self.snippet_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        list_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.snippet_tree.bind("<<TreeviewSelect>>", self.load_snippet_details)
        self.snippet_tree.bind("<Double-1>", self.edit_snippet)

    def setup_right_pane(self):
        right_pane = ttk.Frame(self.content_frame)
        right_pane.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
        details_toolbar = ttk.Frame(right_pane)
        details_toolbar.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(details_toolbar, text="Snippet Details", font=("Arial", 12, "bold")).pack(side=tk.LEFT)
        btn_frame = ttk.Frame(details_toolbar)
        btn_frame.pack(side=tk.RIGHT)
        self.save_btn = ttk.Button(btn_frame, text="💾 Save", command=self.save_snippet, bootstyle=SUCCESS)
        self.save_btn.pack(side=tk.RIGHT, padx=5)
        self.copy_btn = ttk.Button(btn_frame, text="📋 Copy", command=self.copy_to_clipboard, bootstyle=INFO)
        self.copy_btn.pack(side=tk.RIGHT, padx=5)
        self.delete_btn = ttk.Button(btn_frame, text="🗑️ Delete", command=self.delete_snippet, bootstyle=DANGER)
        self.delete_btn.pack(side=tk.RIGHT, padx=5)
        details_frame = ttk.Frame(right_pane)
        details_frame.pack(fill=tk.BOTH, expand=True)
        title_frame = ttk.Frame(details_frame)
        title_frame.pack(fill=tk.X, pady=5)
        ttk.Label(title_frame, text="Title:", font=("Arial", 11)).pack(side=tk.LEFT)
        self.title_entry = ttk.Entry(title_frame, font=("Arial", 11))
        self.title_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))
        lang_tags_frame = ttk.Frame(details_frame)
        lang_tags_frame.pack(fill=tk.X, pady=5)
        lang_frame = ttk.Frame(lang_tags_frame)
        lang_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        ttk.Label(lang_frame, text="Language:", font=("Arial", 11)).pack(side=tk.LEFT)
        self.lang_combo = ttk.Combobox(lang_frame, values=sorted([name for name, _, _, _ in get_all_lexers()]))
        self.lang_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))
        tags_frame = ttk.Frame(lang_tags_frame)
        tags_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))
        ttk.Label(tags_frame, text="Tags:", font=("Arial", 11)).pack(side=tk.LEFT)
        self.tags_entry = ttk.Entry(tags_frame, font=("Arial", 11))
        self.tags_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))
        ttk.Label(details_frame, text="Description:", font=("Arial", 11)).pack(anchor=tk.W, pady=(5, 0))
        self.description_text = scrolledtext.ScrolledText(details_frame, height=3, font=("Arial", 11))
        self.description_text.pack(fill=tk.X, pady=(0, 5))
        code_frame = ttk.Frame(details_frame)
        code_frame.pack(fill=tk.BOTH, expand=True, pady=(5, 0))
        ttk.Label(code_frame, text="Code:", font=("Arial", 11)).pack(anchor=tk.W)
        code_container = ttk.Frame(code_frame)
        code_container.pack(fill=tk.BOTH, expand=True)
        self.code_text = scrolledtext.ScrolledText(code_container, wrap=tk.NONE, font=("Consolas", 12))
        self.code_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        # Bind key release to schedule preview update
        self.code_text.bind("<KeyRelease>", self.schedule_preview_update)
        preview_label = ttk.Label(details_frame, text="Preview (Text Only):", font=("Arial", 11))
        preview_label.pack(anchor=tk.W, pady=(5, 0))
        # Using a simple label for preview instead of HTML
        self.preview_frame = ttk.Label(details_frame, text="", anchor="nw", justify="left", background="black", foreground="white")
        self.preview_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 5))

    def setup_statusbar(self):
        self.statusbar = ttk.Label(self.main_container, text="Ready", relief=tk.SUNKEN, padding=(5, 2))
        self.statusbar.pack(fill=tk.X, pady=(10, 0))
        activity_frame = ttk.Frame(self.main_container)
        activity_frame.pack(fill=tk.X, pady=(5, 0))
        ttk.Label(activity_frame, text="Recent Activity:", font=("Arial", 10, "italic")).pack(side=tk.LEFT)
        self.activity_log = scrolledtext.ScrolledText(activity_frame, height=3, font=("Arial", 9), state=tk.DISABLED)
        self.activity_log.pack(fill=tk.X, expand=True, padx=(5, 0))

    def setup_shortcuts(self):
        self.root.bind("<Control-n>", lambda e: self.new_snippet())
        self.root.bind("<Control-s>", lambda e: self.save_snippet())
        self.root.bind("<Control-f>", lambda e: self.search_entry.focus())
        self.root.bind("<Control-d>", lambda e: self.delete_snippet())
        self.root.bind("<Control-c>", lambda e: self.copy_to_clipboard())

    def schedule_preview_update(self, event=None):
        if self.preview_after_id:
            self.root.after_cancel(self.preview_after_id)
        self.preview_after_id = self.root.after(300, self.update_preview)

    def update_preview(self):
        try:
            code = self.code_text.get("1.0", tk.END).strip()
            language = self.lang_combo.get()
            if code:
                try:
                    lexer = get_lexer_by_name(language.lower(), stripall=True)
                    formatter = HtmlFormatter(style="monokai", full=True)
                    highlighted_code = highlight(code, lexer, formatter)
                    # For this simplified preview, strip HTML tags (or simply display plain code)
                    # Here, we display the plain code.
                    self.preview_frame.config(text=code)
                except Exception as e:
                    self.preview_frame.config(text=code)
                    self.log_activity(f"Error highlighting code: {e}")
            else:
                self.preview_frame.config(text="")
        except Exception as e:
            self.log_activity(f"Error updating preview: {e}")

    def load_snippet_details(self, event=None):
        try:
            selected = self.snippet_tree.selection()
            if not selected:
                return
            snippet_id = self.snippet_tree.item(selected)["values"][0]
            self.cursor.execute("""
                SELECT title, code, language, tags, description, favorite
                FROM snippets WHERE id=?
            """, (snippet_id,))
            snippet = self.cursor.fetchone()
            if snippet:
                self.clear_fields()
                self.title_entry.insert(0, snippet[0])
                self.code_text.insert("1.0", snippet[1])
                self.lang_combo.set(snippet[2])
                self.tags_entry.insert(0, snippet[3])
                if snippet[4]:
                    self.description_text.insert("1.0", snippet[4])
                self.current_favorite = snippet[5]
                self.update_preview()
        except Exception as e:
            self.log_activity(f"Error loading snippet details: {e}")

    def clear_fields(self):
        self.title_entry.delete(0, tk.END)
        self.lang_combo.set("")
        self.tags_entry.delete(0, tk.END)
        self.code_text.delete("1.0", tk.END)
        self.description_text.delete("1.0", tk.END)
        self.preview_frame.config(text="")

    def new_snippet(self):
        self.clear_fields()
        self.title_entry.focus()
        self.snippet_tree.selection_remove(self.snippet_tree.selection())

    def delete_snippet(self):
        try:
            selected = self.snippet_tree.selection()
            if not selected:
                messagebox.showwarning("Delete Error", "No snippet selected!")
                return
            snippet_id = self.snippet_tree.item(selected)["values"][0]
            if messagebox.askyesno("Confirm Delete", "Are you sure you want to delete this snippet?"):
                self.cursor.execute("DELETE FROM snippets WHERE id=?", (snippet_id,))
                self.conn.commit()
                self.log_activity("Snippet deleted successfully!")
                self.clear_fields()
                self.load_snippets()
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred: {e}")

    def copy_to_clipboard(self):
        code = self.code_text.get("1.0", tk.END).strip()
        if code:
            pyperclip.copy(code)
            self.log_activity("Code copied to clipboard!")
        else:
            messagebox.showwarning("Copy Error", "No code to copy!")

    def guess_language(self, code):
        try:
            lexer = guess_lexer(code)
            return lexer.name
        except Exception:
            return "text"

    def toggle_theme(self):
        current_theme = self.root.style.theme.name
        new_theme = "cosmo" if current_theme == "darkly" else "darkly"
        self.root.style.theme_use(new_theme)
        self.log_activity(f"Theme changed to {new_theme}")

    def toggle_favorite(self):
        try:
            selected = self.snippet_tree.selection()
            if not selected:
                messagebox.showwarning("Favorite Error", "No snippet selected!")
                return
            snippet_id = self.snippet_tree.item(selected)["values"][0]
            self.cursor.execute("SELECT favorite FROM snippets WHERE id=?", (snippet_id,))
            current = self.cursor.fetchone()[0]
            new_val = 0 if current else 1
            self.cursor.execute("UPDATE snippets SET favorite=? WHERE id=?", (new_val, snippet_id))
            self.conn.commit()
            self.log_activity("Snippet favorite status updated!")
            self.load_snippets()
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred: {e}")

    def show_settings(self):
        settings_window = tb.Toplevel(self.root)
        settings_window.title("Settings")
        settings_window.geometry("500x400")
        tab_control = ttk.Notebook(settings_window)
        general_tab = ttk.Frame(tab_control)
        tab_control.add(general_tab, text="General")
        backup_frame = ttk.LabelFrame(general_tab, text="Backup", padding=10)
        backup_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Button(backup_frame, text="Export Snippets", command=self.export_snippets).pack(side=tk.LEFT, padx=5)
        ttk.Button(backup_frame, text="Import Snippets", command=self.import_snippets).pack(side=tk.LEFT, padx=5)
        editor_tab = ttk.Frame(tab_control)
        tab_control.add(editor_tab, text="Editor")
        font_frame = ttk.LabelFrame(editor_tab, text="Font Settings", padding=10)
        font_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(font_frame, text="Font Size:").pack(side=tk.LEFT)
        font_size = ttk.Spinbox(font_frame, from_=8, to=24, width=5)
        font_size.pack(side=tk.LEFT, padx=5)
        tab_control.pack(expand=True, fill=tk.BOTH)

    def export_snippets(self):
        file_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if file_path:
            try:
                self.cursor.execute("""
                    SELECT id, title, code, language, tags, description, 
                           favorite, created_at, last_modified 
                    FROM snippets
                """)
                snippets = [dict(zip([col[0] for col in self.cursor.description], row))
                            for row in self.cursor.fetchall()]
                with open(file_path, "w", encoding='utf-8') as file:
                    json.dump(snippets, file, indent=2, ensure_ascii=False)
                self.log_activity("Snippets exported successfully!")
            except Exception as e:
                messagebox.showerror("Export Error", f"Failed to export snippets: {e}")

    def import_snippets(self):
        file_path = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if file_path:
            try:
                with open(file_path, "r", encoding='utf-8') as file:
                    snippets = json.load(file)
                for snippet in snippets:
                    self.cursor.execute("""
                        INSERT INTO snippets (
                            title, code, language, tags, description, 
                            favorite, created_at, last_modified
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        snippet['title'], snippet['code'], snippet['language'],
                        snippet['tags'], snippet.get('description', ''), snippet.get('favorite', 0),
                        snippet.get('created_at', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
                        snippet.get('last_modified', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                    ))
                self.conn.commit()
                self.log_activity("Snippets imported successfully!")
                self.load_snippets()
            except Exception as e:
                messagebox.showerror("Import Error", f"Failed to import snippets: {e}")

    def show_about(self):
        messagebox.showinfo("About", "Code Snippet Manager Pro\nVersion 1.1\n© 2025 Premium Devs Inc.")

    def log_activity(self, message, duration=3000):
        self.statusbar.config(text=message)
        self.activity_log.config(state=tk.NORMAL)
        self.activity_log.insert(tk.END, f"{datetime.now().strftime('%H:%M:%S')} - {message}\n")
        self.activity_log.config(state=tk.DISABLED)
        self.root.after(duration, lambda: self.statusbar.config(text="Ready"))

    def edit_snippet(self, event):
        self.title_entry.focus()

    def on_search_change(self, *args):
        if self.search_timer is not None:
            self.root.after_cancel(self.search_timer)
        self.search_timer = self.root.after(300, self.load_snippets)

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = SnippetManager()
    app.run()
