from tkinter import *
from tkinter import messagebox, ttk
from tkinter import filedialog
import os
import csv
from datetime import datetime
import json
import shutil
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from reportlab.pdfgen import canvas as pdf_canvas
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
import locale
from tkcalendar import DateEntry
import re
from PIL import Image, ImageTk, ImageDraw
import requests
from io import BytesIO

class CustomWidget:
    @staticmethod
    def create_round_rectangle(canvas, x1, y1, x2, y2, radius=25, **kwargs):
        points = [x1+radius, y1,
                 x2-radius, y1,
                 x2, y1,
                 x2, y1+radius,
                 x2, y2-radius,
                 x2, y2,
                 x2-radius, y2,
                 x1+radius, y2,
                 x1, y2,
                 x1, y2-radius,
                 x1, y1+radius,
                 x1, y1]
        return canvas.create_polygon(points, **kwargs, smooth=True)

class ModernEntry(Entry):
    def __init__(self, master, placeholder="", icon=None, *args, **kwargs):
        super().__init__(master, *args, **kwargs)
        
        self.placeholder = placeholder
        self.placeholder_color = "#7f8c8d"
        self.default_fg_color = self["fg"]
        
        if self.placeholder:
            self.insert(0, self.placeholder)
            self.bind("<FocusIn>", self._clear_placeholder)
            self.bind("<FocusOut>", self._add_placeholder)
            
        # Create canvas for custom border animation
        self.canvas = Canvas(master, height=2, bg="white", highlightthickness=0)
        self.canvas.place(x=self.winfo_x(), y=self.winfo_y() + self.winfo_height())
        self.bind("<FocusIn>", self._animate_border_in)
        self.bind("<FocusOut>", self._animate_border_out)
        
    def _clear_placeholder(self, event=None):
        if self.get() == self.placeholder:
            self.delete(0, END)
            self["fg"] = self.default_fg_color
            
    def _add_placeholder(self, event=None):
        if not self.get():
            self.insert(0, self.placeholder)
            self["fg"] = self.placeholder_color
            
    def _animate_border_in(self, event=None):
        self.canvas.create_line(0, 0, self.winfo_width(), 0, fill="#3498db", width=2)
        
    def _animate_border_out(self, event=None):
        self.canvas.create_line(0, 0, self.winfo_width(), 0, fill="#bdc3c7", width=1)

class ModernButton(Button):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.default_bg = kwargs.get('bg', '#3498db')
        self.hover_bg = self._adjust_color(self.default_bg, -20)
        
        self.bind('<Enter>', self._on_enter)
        self.bind('<Leave>', self._on_leave)
        
    def _adjust_color(self, color, amount):
        # Convert hex to RGB
        r = int(color[1:3], 16) + amount
        g = int(color[3:5], 16) + amount
        b = int(color[5:7], 16) + amount
        
        # Clamp values
        r = max(0, min(255, r))
        g = max(0, min(255, g))
        b = max(0, min(255, b))
        
        return f'#{r:02x}{g:02x}{b:02x}'
        
    def _on_enter(self, e):
        self['bg'] = self.hover_bg
        
    def _on_leave(self, e):
        self['bg'] = self.default_bg

class Tooltip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip = None
        self.widget.bind("<Enter>", self.show_tooltip)
        self.widget.bind("<Leave>", self.hide_tooltip)
        
    def show_tooltip(self, event=None):
        x, y, _, _ = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 20
        
        self.tooltip = Toplevel(self.widget)
        self.tooltip.wm_overrideredirect(True)
        self.tooltip.wm_geometry(f"+{x}+{y}")
        
        label = Label(self.tooltip, text=self.tooltip_text, 
                     justify=LEFT, background="#2c3e50", fg="white",
                     relief=SOLID, borderwidth=1,
                     font=("Segoe UI", 9, "normal"))
        label.pack(padx=5, pady=5)
        
    def hide_tooltip(self, event=None):
        if self.tooltip:
            self.tooltip.destroy()
            self.tooltip = None

class EmployeeStats:
    def __init__(self, parent, tree):
        self.parent = parent
        self.tree = tree
        self.fig, self.ax = plt.subplots(figsize=(6, 4))
        
    def show_age_distribution(self):
        current_year = datetime.now().year
        ages = []
        for item in self.tree.get_children():
            values = self.tree.item(item)["values"]
            try:
                birth_year = int(values[2])  # Année column
                age = current_year - birth_year
                ages.append(age)
            except:
                continue
                
        if not ages:
            return
            
        self.ax.clear()
        self.ax.hist(ages, bins=10, color='#3498db', alpha=0.7)
        self.ax.set_title("Distribution d'âge des employés")
        self.ax.set_xlabel("Âge")
        self.ax.set_ylabel("Nombre d'employés")
        
        if not hasattr(self, 'canvas'):
            self.canvas = FigureCanvasTkAgg(self.fig, self.parent)
            self.canvas.get_tk_widget().pack(fill=BOTH, expand=True)
        else:
            self.canvas.draw()

class DataValidator:
    @staticmethod
    def validate_cin(cin):
        # Format: XX123456
        pattern = r'^[A-Z]{2}\d{6}$'
        return bool(re.match(pattern, cin))
        
    @staticmethod
    def validate_year(year):
        try:
            year = int(year)
            current_year = datetime.now().year
            return 1900 <= year <= current_year - 18
        except:
            return False
            
    @staticmethod
    def validate_id(id_str):
        # Format: EMP-2024-001
        pattern = r'^EMP-\d{4}-\d{3}$'
        return bool(re.match(pattern, id_str))

class EmployeeManager:
    def __init__(self):
        self.win = Tk()
        self.win.title("Connexion")
        self.win.geometry("320x280")
        self.win.configure(bg="#f0f4f8")
        
        # Theme state
        self.is_dark_mode = False
        self.themes = {
            "light": {
                "bg": "#f5f6fa",
                "fg": "#2c3e50",
                "input_bg": "white",
                "button_bg": "#3498db"
            },
            "dark": {
                "bg": "#2c3e50",
                "fg": "#ecf0f1",
                "input_bg": "#34495e",
                "button_bg": "#2980b9"
            }
        }
        
        # Language support
        self.current_language = "fr"
        self.load_language()
        
        self.widgets_login = []
        self.setup_login_screen()
        
        # Keyboard shortcuts
        self.win.bind("<Control-s>", lambda e: self.save_current_state())
        self.win.bind("<Control-e>", lambda e: self.export_to_csv())
        self.win.bind("<Control-i>", lambda e: self.import_from_csv())
        self.win.bind("<Control-b>", lambda e: self.backup_data())
        self.win.bind("<Control-r>", lambda e: self.restore_data())
        self.win.bind("<Control-d>", lambda e: self.toggle_theme())
        self.win.bind("<Control-p>", lambda e: self.export_to_pdf())
        self.win.bind("<Control-m>", lambda e: self.send_email_report())
        
        # Auto-save timer
        self.auto_save_id = None
        self.start_auto_save()

    def load_language(self):
        self.translations = {
            "fr": {
                "login_title": "Système de Gestion",
                "username": "Utilisateur",
                "password": "Mot de passe",
                "login_button": "Se Connecter",
                "search_placeholder": "Rechercher un employé...",
                "add_button": "Ajouter",
                "clear_button": "Effacer",
                "export_button": "Exporter",
                "name_field": "Nom",
                "cin_field": "CIN",
                "year_field": "Année",
                "id_field": "ID"
            },
            "en": {
                "login_title": "Management System",
                "username": "Username",
                "password": "Password",
                "login_button": "Login",
                "search_placeholder": "Search employee...",
                "add_button": "Add",
                "clear_button": "Clear",
                "export_button": "Export",
                "name_field": "Name",
                "cin_field": "ID Number",
                "year_field": "Year",
                "id_field": "ID"
            }
        }

    def setup_login_screen(self):
        # Create gradient background
        gradient_frame = Frame(self.win, bg="#f0f4f8")
        gradient_frame.place(relwidth=1, relheight=1)
        
        # Login Frame with rounded corners
        login_frame = Frame(gradient_frame, bg="white", padx=20, pady=20)
        login_frame.place(relx=0.5, rely=0.5, anchor=CENTER)
        
        # Add shadow effect
        shadow_canvas = Canvas(login_frame, bg="white", highlightthickness=0)
        shadow_canvas.place(relwidth=1, relheight=1)
        CustomWidget.create_round_rectangle(shadow_canvas, 0, 0, 300, 250, 
                                         radius=15, fill="white")
        
        # Title with modern font
        title_label = Label(login_frame, 
                          text=self.translations[self.current_language]["login_title"],
                          font=("Segoe UI", 20, "bold"), 
                          bg="white", fg="#2c3e50")
        title_label.pack(pady=(0, 20))
        
        # Modern username entry with icon
        self.username_entry = ModernEntry(login_frame, 
                                        placeholder=self.translations[self.current_language]["username"],
                                        font=("Segoe UI", 10))
        self.username_entry.pack(fill=X, pady=5)
        
        # Modern password entry with icon
        self.password_entry = ModernEntry(login_frame,
                                        placeholder=self.translations[self.current_language]["password"],
                                        show="*", font=("Segoe UI", 10))
        self.password_entry.pack(fill=X, pady=5)
        
        # Modern login button with hover effect
        login_button = ModernButton(login_frame, 
                                  text=self.translations[self.current_language]["login_button"],
                                  font=("Segoe UI", 10, "bold"),
                                  bg="#3498db", fg="white",
                                  command=self.verify_login,
                                  relief=FLAT, width=20)
        login_button.pack(pady=(20, 0))
        
        # Language switcher
        lang_frame = Frame(login_frame, bg="white")
        lang_frame.pack(pady=(20, 0))
        
        fr_btn = ModernButton(lang_frame, text="FR", width=3,
                            command=lambda: self.change_language("fr"))
        fr_btn.pack(side=LEFT, padx=5)
        
        en_btn = ModernButton(lang_frame, text="EN", width=3,
                            command=lambda: self.change_language("en"))
        en_btn.pack(side=LEFT, padx=5)
        
        # Bind events
        self.username_entry.bind("<Return>", lambda e: self.password_entry.focus())
        self.password_entry.bind("<Return>", lambda e: self.verify_login())
        
        self.widgets_login.extend([login_frame])
        self.username_entry.focus()

    def verify_login(self, event=None):
        if self.username_entry.get() == "admin" and self.password_entry.get() == "pass123":
            self.setup_main_application()
        else:
            messagebox.showerror("Erreur", "Identifiants incorrects!")
            self.username_entry.delete(0, END)
            self.password_entry.delete(0, END)
            self.username_entry.focus()

    def setup_main_application(self):
        # Hide login widgets
        for widget in self.widgets_login:
            widget.destroy()
        
        self.win.title("Gestion des Employés")
        self.win.geometry("1024x768")
        self.win.configure(bg="#f5f6fa")
        
        # Create main container with modern design
        self.setup_menu()
        self.create_main_interface()
        self.create_dashboard()
        self.setup_status_bar()
        
    def setup_menu(self):
        menubar = Menu(self.win)
        self.win.config(menu=menubar)
        
        # File menu
        file_menu = Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Fichier", menu=file_menu)
        file_menu.add_command(label="Importer CSV (Ctrl+I)", command=self.import_from_csv)
        file_menu.add_command(label="Exporter CSV (Ctrl+E)", command=self.export_to_csv)
        file_menu.add_command(label="Exporter PDF (Ctrl+P)", command=self.export_to_pdf)
        file_menu.add_separator()
        file_menu.add_command(label="Sauvegarder (Ctrl+S)", command=self.save_current_state)
        file_menu.add_command(label="Backup (Ctrl+B)", command=self.backup_data)
        file_menu.add_command(label="Restaurer (Ctrl+R)", command=self.restore_data)
        file_menu.add_separator()
        file_menu.add_command(label="Envoyer Rapport (Ctrl+M)", command=self.send_email_report)
        file_menu.add_separator()
        file_menu.add_command(label="Quitter", command=self.win.quit)
        
        # View menu
        view_menu = Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Affichage", menu=view_menu)
        view_menu.add_command(label="Mode Sombre (Ctrl+D)", command=self.toggle_theme)
        view_menu.add_command(label="Statistiques", command=self.show_statistics)
        
        # Language menu
        lang_menu = Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Langue", menu=lang_menu)
        lang_menu.add_command(label="Français", command=lambda: self.change_language("fr"))
        lang_menu.add_command(label="English", command=lambda: self.change_language("en"))

    def create_main_interface(self):
        # Main container with modern padding
        main_container = Frame(self.win, bg="#f5f6fa")
        main_container.pack(fill=BOTH, expand=True, padx=30, pady=20)
        
        # Search frame with modern design
        search_frame = Frame(main_container, bg="#f5f6fa")
        search_frame.pack(fill=X, pady=(0, 20))
        
        self.search_var = StringVar()
        self.search_var.trace('w', self.search_employees)
        search_entry = ModernEntry(search_frame, 
                                 placeholder=self.translations[self.current_language]["search_placeholder"],
                                 font=("Segoe UI", 10))
        search_entry.pack(side=LEFT, fill=X, expand=True)
        
        # Advanced filters
        self.setup_filters(search_frame)
        
        # Form frame with modern design
        form_frame = Frame(main_container, bg="#f5f6fa")
        form_frame.pack(fill=X, pady=(0, 20))
        
        # Employee form with validation
        self.employee_entries = {}
        fields = [
            ("name", self.translations[self.current_language]["name_field"]),
            ("cin", self.translations[self.current_language]["cin_field"]),
            ("year", self.translations[self.current_language]["year_field"]),
            ("id", self.translations[self.current_language]["id_field"])
        ]
        
        for field_id, field_label in fields:
            entry_frame = Frame(form_frame, bg="#f5f6fa")
            entry_frame.pack(fill=X, pady=5)
            
            Label(entry_frame, text=f"{field_label}:", 
                  font=("Segoe UI", 10), bg="#f5f6fa", 
                  fg="#2c3e50").pack(anchor=W)
                  
            entry = ModernEntry(entry_frame, font=("Segoe UI", 10))
            entry.pack(fill=X, pady=(2, 0))
            self.employee_entries[field_id] = entry
            
            # Add validation
            if field_id == "cin":
                Tooltip(entry, "Format: XX123456")
                entry.bind('<FocusOut>', lambda e: self.validate_cin())
            elif field_id == "year":
                Tooltip(entry, "Année de naissance (1900-2006)")
                entry.bind('<FocusOut>', lambda e: self.validate_year())
            elif field_id == "id":
                Tooltip(entry, "Format: EMP-2024-001")
                entry.bind('<FocusOut>', lambda e: self.validate_id())
        
        # Buttons frame with modern design
        buttons_frame = Frame(main_container, bg="#f5f6fa")
        buttons_frame.pack(fill=X, pady=(0, 20))
        
        # Modern action buttons
        self.create_modern_button(buttons_frame, "Ajouter", self.add_employee, "#2ecc71")
        self.create_modern_button(buttons_frame, "Effacer", self.clear_form, "#95a5a6")
        self.create_modern_button(buttons_frame, "Exporter", self.export_to_csv, "#3498db")
        
        # Modern Treeview
        self.setup_treeview(main_container)

    def setup_filters(self, parent):
        filters_frame = Frame(parent, bg="#f5f6fa")
        filters_frame.pack(side=RIGHT, padx=(10, 0))
        
        # Year range filter
        year_frame = Frame(filters_frame, bg="#f5f6fa")
        year_frame.pack(side=LEFT, padx=5)
        
        Label(year_frame, text="Année:", bg="#f5f6fa").pack(side=LEFT)
        self.year_filter = ttk.Combobox(year_frame, width=6)
        self.year_filter.pack(side=LEFT)
        self.year_filter['values'] = tuple(range(1900, datetime.now().year + 1))
        self.year_filter.bind('<<ComboboxSelected>>', self.apply_filters)
        
        # Department filter (if you add department field)
        dept_frame = Frame(filters_frame, bg="#f5f6fa")
        dept_frame.pack(side=LEFT, padx=5)
        
        Label(dept_frame, text="Département:", bg="#f5f6fa").pack(side=LEFT)
        self.dept_filter = ttk.Combobox(dept_frame, width=15)
        self.dept_filter.pack(side=LEFT)
        self.dept_filter['values'] = ("Tous", "RH", "IT", "Finance", "Marketing")
        self.dept_filter.set("Tous")
        self.dept_filter.bind('<<ComboboxSelected>>', self.apply_filters)

    def setup_treeview(self, parent):
        # Create Treeview with modern style
        style = ttk.Style()
        style.configure("Custom.Treeview",
                       background="#ffffff",
                       foreground="#2c3e50",
                       fieldbackground="#ffffff",
                       rowheight=30)
        style.configure("Custom.Treeview.Heading",
                       background="#3498db",
                       foreground="white",
                       relief="flat")
        style.map("Custom.Treeview.Heading",
                 background=[('active', '#2980b9')])
        
        # Create Treeview
        self.tree = ttk.Treeview(parent, style="Custom.Treeview",
                                columns=("Nom", "CIN", "Année", "ID"),
                                show="headings", height=15)
        
        # Configure columns
        for col in ("Nom", "CIN", "Année", "ID"):
            self.tree.heading(col, text=col, 
                            command=lambda c=col: self.sort_treeview(c))
            self.tree.column(col, width=150)
        
        # Add scrollbars
        yscroll = ttk.Scrollbar(parent, orient="vertical", 
                               command=self.tree.yview)
        xscroll = ttk.Scrollbar(parent, orient="horizontal", 
                               command=self.tree.xview)
        
        self.tree.configure(yscrollcommand=yscroll.set,
                          xscrollcommand=xscroll.set)
        
        # Pack everything
        self.tree.pack(side=LEFT, fill=BOTH, expand=True)
        yscroll.pack(side=RIGHT, fill=Y)
        xscroll.pack(side=BOTTOM, fill=X)
        
        # Bind events
        self.tree.bind("<Delete>", self.delete_selected)
        self.tree.bind("<Button-3>", self.create_context_menu)
        self.tree.bind("<Double-1>", self.edit_selected)
        
        # Load initial data
        self.load_employees()

    def create_dashboard(self):
        # Create dashboard window
        self.dashboard_win = Toplevel(self.win)
        self.dashboard_win.title("Tableau de Bord")
        self.dashboard_win.geometry("800x600")
        
        # Statistics frame
        stats_frame = Frame(self.dashboard_win)
        stats_frame.pack(fill=BOTH, expand=True, padx=20, pady=20)
        
        # Employee count
        count_frame = Frame(stats_frame, relief=RIDGE, bd=1)
        count_frame.pack(fill=X, pady=10)
        
        Label(count_frame, text="Nombre total d'employés:",
              font=("Segoe UI", 12, "bold")).pack(pady=5)
        self.employee_count_label = Label(count_frame, text="0",
                                        font=("Segoe UI", 24))
        self.employee_count_label.pack(pady=5)
        
        # Age distribution chart
        self.stats = EmployeeStats(stats_frame, self.tree)
        self.stats.show_age_distribution()
        
        # Update dashboard
        self.update_dashboard()

    def setup_status_bar(self):
        status_frame = Frame(self.win, bg="#f5f6fa")
        status_frame.pack(fill=X, side=BOTTOM, pady=5)
        
        self.status_var = StringVar()
        status_label = Label(status_frame, textvariable=self.status_var,
                           font=("Segoe UI", 9), bg="#f5f6fa", fg="#7f8c8d")
        status_label.pack(side=LEFT, padx=10)
        
        # Auto-save indicator
        self.auto_save_var = StringVar()
        self.auto_save_var.set("Auto-sauvegarde activée")
        auto_save_label = Label(status_frame, textvariable=self.auto_save_var,
                              font=("Segoe UI", 9), bg="#f5f6fa", fg="#27ae60")
        auto_save_label.pack(side=RIGHT, padx=10)

    def add_employee(self):
        # Validate form
        for field, entry in self.employee_entries.items():
            if not entry.get().strip():
                messagebox.showwarning("Validation", f"Le champ {field} est requis!")
                entry.focus()
                return
        
        # Add to treeview
        values = [entry.get().strip() for entry in self.employee_entries.values()]
        self.tree.insert("", END, values=values)
        
        # Save to file
        with open("employes.txt", "a", encoding="utf-8") as f:
            f.write(f"Nom: {values[0]}, CIN: {values[1]}, Année: {values[2]}, ID: {values[3]}\n")
        
        self.clear_form()
        self.update_status("Employé ajouté avec succès!")

    def clear_form(self):
        for entry in self.employee_entries.values():
            entry.delete(0, END)
        self.employee_entries["nom"].focus()

    def delete_selected(self, event=None):
        selected = self.tree.selection()
        if not selected:
            return
        
        if messagebox.askyesno("Confirmation", "Voulez-vous vraiment supprimer cet employé?"):
            self.tree.delete(selected)
            self.save_current_state()
            self.update_status("Employé supprimé!")

    def search_employees(self, *args):
        search_term = self.search_var.get().lower()
        self.tree.delete(*self.tree.get_children())
        
        with open("employes.txt", "r", encoding="utf-8") as f:
            for line in f:
                if search_term in line.lower():
                    parts = line.strip().split(", ")
                    values = [p.split(": ")[1] for p in parts]
                    self.tree.insert("", END, values=values)

    def export_to_csv(self):
        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if filename:
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["Nom", "CIN", "Année", "ID"])
                for item in self.tree.get_children():
                    writer.writerow(self.tree.item(item)["values"])
            self.update_status(f"Données exportées vers {filename}")

    def sort_treeview(self, col):
        items = [(self.tree.set(item, col), item) for item in self.tree.get_children("")]
        items.sort()
        for index, (_, item) in enumerate(items):
            self.tree.move(item, "", index)

    def load_employees(self):
        if os.path.exists("employes.txt"):
            with open("employes.txt", "r", encoding="utf-8") as f:
                for line in f:
                    parts = line.strip().split(", ")
                    values = [p.split(": ")[1] for p in parts]
                    self.tree.insert("", END, values=values)

    def save_current_state(self):
        with open("employes.txt", "w", encoding="utf-8") as f:
            for item in self.tree.get_children():
                values = self.tree.item(item)["values"]
                f.write(f"Nom: {values[0]}, CIN: {values[1]}, Année: {values[2]}, ID: {values[3]}\n")

    def update_status(self, message=None):
        count = len(self.tree.get_children())
        status = f"{count} employé{'s' if count > 1 else ''} | "
        status += message if message else datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        self.status_var.set(status)

    def create_context_menu(self, event):
        context_menu = Menu(self.win, tearoff=0)
        context_menu.add_command(label="Modifier", command=self.edit_selected)
        context_menu.add_command(label="Supprimer", command=lambda: self.delete_selected())
        context_menu.add_separator()
        context_menu.add_command(label="Copier", command=self.copy_selected)
        
        try:
            context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            context_menu.grab_release()

    def edit_selected(self):
        selected = self.tree.selection()
        if not selected:
            return
            
        item = self.tree.item(selected[0])
        values = item['values']
        
        for field, value in zip(self.employee_entries.keys(), values):
            self.employee_entries[field].delete(0, END)
            self.employee_entries[field].insert(0, value)
        
        self.tree.delete(selected)
        self.employee_entries["nom"].focus()

    def copy_selected(self):
        selected = self.tree.selection()
        if not selected:
            return
            
        item = self.tree.item(selected[0])
        values = item['values']
        self.win.clipboard_clear()
        self.win.clipboard_append(", ".join(str(v) for v in values))

    def toggle_theme(self, event=None):
        self.is_dark_mode = not self.is_dark_mode
        theme = self.themes["dark" if self.is_dark_mode else "light"]
        
        self.win.configure(bg=theme["bg"])
        for widget in self.win.winfo_children():
            if isinstance(widget, (Frame, Label)):
                widget.configure(bg=theme["bg"], fg=theme["fg"])
            elif isinstance(widget, Entry):
                widget.configure(bg=theme["input_bg"], fg=theme["fg"])
            elif isinstance(widget, Button):
                widget.configure(bg=theme["button_bg"])
        
        style = ttk.Style()
        if self.is_dark_mode:
            style.configure("Treeview", background=theme["input_bg"], 
                          foreground=theme["fg"], fieldbackground=theme["input_bg"])
        else:
            style.configure("Treeview", background="white", 
                          foreground=theme["fg"], fieldbackground="white")

    def import_from_csv(self, event=None):
        filename = filedialog.askopenfilename(
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if filename:
            try:
                with open(filename, 'r', newline='', encoding='utf-8') as f:
                    reader = csv.reader(f)
                    next(reader)  # Skip header
                    for row in reader:
                        self.tree.insert("", END, values=row)
                self.save_current_state()
                self.update_status(f"Données importées depuis {filename}")
            except Exception as e:
                messagebox.showerror("Erreur", f"Erreur lors de l'importation: {str(e)}")

    def backup_data(self, event=None):
        if not os.path.exists("employes.txt"):
            messagebox.showwarning("Backup", "Aucune donnée à sauvegarder.")
            return
            
        backup_dir = "backups"
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = os.path.join(backup_dir, f"employes_backup_{timestamp}.txt")
        
        try:
            shutil.copy2("employes.txt", backup_file)
            self.update_status(f"Backup créé: {backup_file}")
        except Exception as e:
            messagebox.showerror("Erreur", f"Erreur lors du backup: {str(e)}")

    def restore_data(self, event=None):
        backup_dir = "backups"
        if not os.path.exists(backup_dir):
            messagebox.showwarning("Restauration", "Aucun backup disponible.")
            return
            
        backup_files = [f for f in os.listdir(backup_dir) if f.startswith("employes_backup_")]
        if not backup_files:
            messagebox.showwarning("Restauration", "Aucun backup trouvé.")
            return
            
        # Trier par date (plus récent en premier)
        backup_files.sort(reverse=True)
        
        # Créer une fenêtre de sélection
        restore_win = Toplevel(self.win)
        restore_win.title("Restaurer un backup")
        restore_win.geometry("400x300")
        
        Label(restore_win, text="Sélectionner un backup à restaurer:", 
              font=("Segoe UI", 10)).pack(pady=10)
              
        listbox = Listbox(restore_win, font=("Segoe UI", 10))
        listbox.pack(fill=BOTH, expand=True, padx=10, pady=5)
        
        for backup_file in backup_files:
            listbox.insert(END, backup_file)
            
        def do_restore():
            selection = listbox.curselection()
            if not selection:
                return
                
            backup_file = os.path.join(backup_dir, listbox.get(selection[0]))
            try:
                shutil.copy2(backup_file, "employes.txt")
                self.load_employees()
                self.update_status(f"Données restaurées depuis {backup_file}")
                restore_win.destroy()
            except Exception as e:
                messagebox.showerror("Erreur", f"Erreur lors de la restauration: {str(e)}")
                
        Button(restore_win, text="Restaurer", command=do_restore,
               font=("Segoe UI", 10, "bold"), bg="#3498db", fg="white").pack(pady=10)

    def validate_cin(self):
        cin = self.employee_entries["cin"].get().strip()
        if not DataValidator.validate_cin(cin):
            self.employee_entries["cin"].configure(fg="red")
            Tooltip(self.employee_entries["cin"], "Format invalide! Exemple: XX123456")
            return False
        self.employee_entries["cin"].configure(fg="#2c3e50")
        return True

    def validate_year(self):
        year = self.employee_entries["year"].get().strip()
        if not DataValidator.validate_year(year):
            self.employee_entries["year"].configure(fg="red")
            Tooltip(self.employee_entries["year"], "Année invalide! (1900-2006)")
            return False
        self.employee_entries["year"].configure(fg="#2c3e50")
        return True

    def validate_id(self):
        id_str = self.employee_entries["id"].get().strip()
        if not DataValidator.validate_id(id_str):
            self.employee_entries["id"].configure(fg="red")
            Tooltip(self.employee_entries["id"], "Format invalide! Exemple: EMP-2024-001")
            return False
        self.employee_entries["id"].configure(fg="#2c3e50")
        return True

    def apply_filters(self, event=None):
        year = self.year_filter.get()
        dept = self.dept_filter.get()
        
        self.tree.delete(*self.tree.get_children())
        
        with open("employes.txt", "r", encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split(", ")
                values = [p.split(": ")[1] for p in parts]
                
                # Apply year filter
                if year and values[2] != year:
                    continue
                    
                # Apply department filter (if you add department field)
                if dept != "Tous" and len(values) > 4 and values[4] != dept:
                    continue
                    
                self.tree.insert("", END, values=values)

    def export_to_pdf(self, event=None):
        filename = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")]
        )
        if not filename:
            return
            
        # Create PDF
        doc = SimpleDocTemplate(filename, pagesize=letter)
        elements = []
        
        # Title
        title = "Liste des Employés"
        elements.append(Paragraph(title, getSampleStyleSheet()["Title"]))
        
        # Table data
        data = [["Nom", "CIN", "Année", "ID"]]
        for item in self.tree.get_children():
            data.append(self.tree.item(item)["values"])
            
        # Create table
        table = Table(data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.blue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 14),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        elements.append(table)
        
        # Build PDF
        doc.build(elements)
        self.update_status(f"PDF exporté: {filename}")

    def send_email_report(self, event=None):
        # Create email dialog
        email_win = Toplevel(self.win)
        email_win.title("Envoyer Rapport")
        email_win.geometry("400x300")
        
        # Email form
        Label(email_win, text="Destinataire:", font=("Segoe UI", 10)).pack(anchor=W, padx=10, pady=5)
        email_entry = ModernEntry(email_win, placeholder="email@example.com")
        email_entry.pack(fill=X, padx=10)
        
        Label(email_win, text="Sujet:", font=("Segoe UI", 10)).pack(anchor=W, padx=10, pady=5)
        subject_entry = ModernEntry(email_win, placeholder="Rapport des employés")
        subject_entry.pack(fill=X, padx=10)
        
        Label(email_win, text="Message:", font=("Segoe UI", 10)).pack(anchor=W, padx=10, pady=5)
        message_text = Text(email_win, height=6, font=("Segoe UI", 10))
        message_text.pack(fill=BOTH, expand=True, padx=10, pady=5)
        
        def send_email():
            # Get form data
            recipient = email_entry.get()
            subject = subject_entry.get()
            message = message_text.get("1.0", END)
            
            try:
                # Create temporary PDF
                temp_pdf = "temp_report.pdf"
                self.export_to_pdf(temp_pdf)
                
                # Create email
                msg = MIMEMultipart()
                msg["From"] = "your_email@example.com"  # Replace with actual email
                msg["To"] = recipient
                msg["Subject"] = subject
                
                msg.attach(MIMEText(message, "plain"))
                
                # Attach PDF
                with open(temp_pdf, "rb") as f:
                    pdf_attachment = MIMEApplication(f.read(), _subtype="pdf")
                    pdf_attachment.add_header(
                        "Content-Disposition", "attachment", filename="rapport_employes.pdf")
                    msg.attach(pdf_attachment)
                
                # Send email (configure your SMTP settings)
                # with smtplib.SMTP("smtp.gmail.com", 587) as server:
                #     server.starttls()
                #     server.login("your_email@example.com", "your_password")
                #     server.send_message(msg)
                
                os.remove(temp_pdf)
                email_win.destroy()
                self.update_status("Rapport envoyé par email!")
                
            except Exception as e:
                messagebox.showerror("Erreur", f"Erreur d'envoi: {str(e)}")
        
        ModernButton(email_win, text="Envoyer", command=send_email,
                    bg="#3498db", fg="white").pack(pady=10)

    def show_statistics(self):
        if hasattr(self, 'dashboard_win'):
            self.dashboard_win.lift()
        else:
            self.create_dashboard()

    def update_dashboard(self):
        # Update employee count
        count = len(self.tree.get_children())
        self.employee_count_label.config(text=str(count))
        
        # Update age distribution
        self.stats.show_age_distribution()
        
        # Schedule next update
        self.win.after(5000, self.update_dashboard)

    def start_auto_save(self):
        def auto_save():
            self.save_current_state()
            self.auto_save_var.set("Sauvegardé à " + datetime.now().strftime("%H:%M:%S"))
            self.auto_save_id = self.win.after(300000, auto_save)  # 5 minutes
        
        self.auto_save_id = self.win.after(300000, auto_save)

    def change_language(self, lang):
        self.current_language = lang
        # Update all text elements
        # This is a simplified version - you would need to update all text elements
        self.update_interface_language()

    def update_interface_language(self):
        # Update menu labels
        # Update button texts
        # Update field labels
        # This would need to be implemented based on your translations dictionary
        pass

    def create_modern_button(self, parent, text, command, color):
        btn = ModernButton(parent, text=text, font=("Segoe UI", 10, "bold"),
                          bg=color, fg="white", command=command,
                          relief=FLAT)
        btn.pack(side=LEFT, padx=5)
        return btn

    def run(self):
        self.win.mainloop()

if __name__ == "__main__":
    app = EmployeeManager()
    app.run()
