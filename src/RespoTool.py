# -*- coding: utf-8 -*-
# !python3

import json
import logging
import os
import platform
import tkinter as tk
import tkinter.filedialog as fdialog
import tkinter.messagebox as mbox
import tkinter.ttk as ttk

import pyperclip

import archives
import signalement
import sigparser
import utils
from _meta import __appname__, __version__
from widgets import searchbar, siglist, statusbar
from widgets.dialogs.infodialog import InfoDialog


def fix_treeview():
    def fixed_map(option):
        # Fix for setting text colour for Tkinter 8.6.9
        # From: https://bugs.python.org/issue36468
        return [elm for elm in style.map("Treeview", query_opt=option) if
                elm[:2] != ("!disabled", "!selected")]

    style = ttk.Style()
    style.map("Treeview", foreground=fixed_map("foreground"), background=fixed_map("background"))


class RespoTool(tk.Tk):
    def __init__(self, app_title, *, session_path=None, archives_dir=None, archives_pattern=None, auto_import=True,
                 warning_message=""):
        super().__init__()
        self.app_title = app_title
        self.session_path = session_path
        self.archives_dir = archives_dir
        self.auto_import = auto_import
        self.warning_message = warning_message
        self.current_respo = tk.StringVar()
        with open(utils.resource_path("data/respomaps.json"), "r", encoding="utf-8") as f:
            self.respomaps = json.load(f)
        with open(utils.resource_path("data/contact.json"), "r", encoding="utf-8") as f:
            self.contact = json.load(f)
        self.signalements = []
        self.archives = archives.Archives(archives_dir, archives_pattern)

        # Rendering
        fix_treeview()
        self._setup_widgets()
        self.title(self.app_title)
        self.update_idletasks()
        self.minsize(742, self.winfo_reqheight())
        try:
            self.tk.call("encoding", "system", "utf-8")
            path = utils.resource_path("data/img/respotool.ico")
            self.iconbitmap(default=path)
        except Exception as e:
            logging.error(e)

        # Imports
        if self.auto_import:
            if self.session_path and os.path.exists(self.session_path):
                self.import_save(self.session_path)
        self.archives.open()

        # Bindings
        self.bind("<Control-s>", lambda _: self.export_save())
        self.bind("<Control-o>", lambda _: self.import_save())
        self.bind("<Control-f>", lambda _: self.focus_searchbar())
        self.bind("<Control-q>", lambda _: self.quit())
        self.main_frame.bind("<Control-v>", lambda _: self.append_clipboard())
        self.main_frame.bind("<Button-1>", lambda _: self.clear_focus())
        self.tree_sig.tree.bind("<<TreeviewSelect>>", lambda _: self.selection_handler(), add="+")
        self.current_respo.trace("w", lambda *_: logging.debug("Setting respomap={}".format(self.current_respo.get())))
        self.protocol("WM_DELETE_WINDOW", self.quit)

        # Warnings
        if self.warning_message:
            dialog_title = self.app_title
            info = InfoDialog(self, dialog_title=dialog_title, body_text=self.warning_message)
            info.spawn()

    def _setup_widgets(self):
        self.statusbar = statusbar.StatusBar(self)
        self.statusbar.pack(side="bottom", fill="x")
        self.main_frame = ttk.Frame(self)
        self.main_frame.pack(fill="both", expand=True, pady=5, padx=5)

        # -------------------------------------------- IMPORT / EXPORT --------------------------------------------- #

        self.labelframe_new = ttk.Labelframe(self.main_frame, text="Nouvelle session")
        button_new_file = ttk.Button(self.labelframe_new, text="Fichier", command=self.new_file)
        button_new_file.pack(fill="both", expand=True, side="left", padx=(7, 0), pady=(0, 7))
        button_new_cb = ttk.Button(self.labelframe_new, text="Presse-papiers", command=self.new_clipboard)
        button_new_cb.pack(fill="both", expand=True, side="right", padx=(0, 7), pady=(0, 7))

        self.labelframe_append = ttk.Labelframe(self.main_frame, text="Ajouter nouveaux sigs")
        button_append_file = ttk.Button(self.labelframe_append, text="Fichier", command=self.append_file)
        button_append_file.pack(fill="both", expand=True, side="left", padx=(7, 0), pady=(0, 7))
        button_append_cb = ttk.Button(self.labelframe_append, text="Presse-papiers", command=self.append_clipboard)
        button_append_cb.pack(fill="both", expand=True, side="right", padx=(0, 7), pady=(0, 7))

        self.labelframe_session = ttk.Labelframe(self.main_frame, text="Importer / Exporter session")
        button_import = ttk.Button(self.labelframe_session, text="Importer", command=self.import_save)
        button_import.pack(fill="both", expand=True, side="left", padx=(7, 0), pady=(0, 7))
        button_export = ttk.Button(self.labelframe_session, text="Exporter", command=self.export_save)
        button_export.pack(fill="both", expand=True, side="right", padx=(0, 7), pady=(0, 7))

        button_new_file.configure(state="disabled")
        button_new_cb.configure(state="disabled")
        button_append_file.configure(state="disabled")

        # ----------------------------------------- CURRENT RESPO & SEARCH ----------------------------------------- #

        self.frame_respo = ttk.Frame(self.main_frame)
        self.icon_respo = tk.PhotoImage(file=utils.resource_path("data/img/shield_respo.png"))
        lbl_icon_respo = ttk.Label(self.frame_respo, image=self.icon_respo)
        lbl_icon_respo.pack(side="left")
        label_respo = ttk.Label(self.frame_respo, text="Respomap  :  ")
        label_respo.pack(side="left")
        self.dropdown_respo = ttk.Combobox(self.frame_respo, state="readonly", textvariable=self.current_respo)
        self.dropdown_respo.pack(side="right")
        self.dropdown_respo["values"] = self.respomaps["main"]  # comptes principaux
        self.dropdown_respo.textvariable = self.current_respo

        self.frame_search = ttk.Frame(self.main_frame)
        self.label_matches = ttk.Label(self.frame_search, foreground="grey40")
        self.label_matches.pack(side="left", padx=(0, 5))
        placeholder_options = {
            "text": " Rechercher"
        }
        icon_options = {
            "path": utils.resource_path("data/img/search1.png"),
            "alt": utils.resource_path("data/img/search2.png")
        }
        self.searchbar = searchbar.SearchBar(self.frame_search, placeholder_options=placeholder_options,
                                             icon_options=icon_options, width=30)
        self.searchbar.pack(side="right")

        # ---------------------------------------------- SIGNALEMENTS ---------------------------------------------- #

        headers = ["Date", "Auteur", "Code", "Flag", "Description", "Statut", "Respomap(s)"]
        column_widths = [55, 85, 100, 80, 400, 350, 100]
        sort_keys = [
            lambda x: (int(x[0].split("/")[1]), int(x[0].split("/")[0])),
            lambda x: x[0].lower(),
            lambda x: x[0].lower(),
            lambda x: x[0].lower(),
            lambda x: x[0].lower(),
            lambda x: x[0].lower(),
            lambda x: x[0].lower(),
        ]
        stretch_bools = [False, False, False, False, True, True, True]
        index_options = {
            "show": True,
            "header": "#",
            "width": 35,
            "sort": lambda x: int(x[0]),
            "stretch": False
        }
        exclude = [placeholder_options["text"]]
        search_tags = ["num", "date", "auteur", "code", "flag", "desc", "statut", "respo"]
        self.tree_sig = siglist.Siglist(self.main_frame, signalements=self.signalements, archives=self.archives,
                                        respomap_widget=self.dropdown_respo, statusbar=self.statusbar,
                                        headers=headers, sort_keys=sort_keys, stretch_bools=stretch_bools, height=20,
                                        index_options=index_options, sortable=False, column_widths=column_widths,
                                        match_template="{} sur {}", search_excludes=exclude, search_tags=search_tags)
        self.searchbar.entry.configure(textvariable=self.tree_sig._search_query)
        self.label_matches.configure(textvariable=self.tree_sig._matches_label)

        # ------------------------------------------------ ACTIONS ------------------------------------------------- #

        self.frame_actions = ttk.Frame(self.main_frame)
        self.button_generate_mp = ttk.Button(self.frame_actions, command=self.generate_contact_message)
        self.button_generate_mp.pack(side="left")
        self.button_archive_selection = ttk.Button(self.frame_actions, command=self.archive_selection)
        self.button_archive_selection.pack(side="right")

        self.button_generate_mp.configure(text="Générer MP", width=16, state="disabled")
        self.button_archive_selection.configure(text="Archiver sélection", width=16, state="disabled")

        # ------------------------------------------- WIDGETS PLACEMENT -------------------------------------------- #

        self.labelframe_new.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        self.labelframe_append.grid(row=0, column=1, sticky="nsew", padx=5)
        self.labelframe_session.grid(row=0, column=2, sticky="nsew", padx=(5, 0))
        self.frame_respo.grid(row=1, column=0, sticky="w", pady=10)
        self.frame_search.grid(row=1, column=2, sticky="e", padx=(0, 17), pady=10)
        self.tree_sig.grid(row=2, column=0, columnspan=3, sticky="nsew", pady=(0, 10))
        self.frame_actions.grid(row=3, column=1)

        self.main_frame.grid_rowconfigure(2, weight=1)
        self.main_frame.grid_columnconfigure((0, 1, 2), weight=1, uniform="_")
        # Changes the widget stack order so that pressing Tab after setting the Respomap brings the focus directly to
        # the table instead of giving the focus to the search bar. Not doing so would clear the selected items in the
        # table upon entering the search bar, which is unwanted. This is particularly useful when one forgets to set
        # the Respomap value and is prompted with it before being able to edit a status.
        self.frame_search.lower()
        # Needed to rewrite the placeholder because we hooked an empty StringVar that erased it
        self.searchbar.focus_out(None)

    def selection_handler(self):
        selection = self.tree_sig.tree.selection()
        if len(selection) == 0:
            self.button_generate_mp.configure(state="disabled")
            self.button_archive_selection.configure(state="disabled")
        elif len(selection) == 1:
            self.button_generate_mp.configure(state="enabled")
            self.button_archive_selection.configure(state="enabled")
        elif len(selection) > 1:
            self.button_generate_mp.configure(state="disabled")
            self.button_archive_selection.configure(state="enabled")

    def new_file(self):
        filename = fdialog.askopenfilename(filetypes=(("Text Files", "*.txt"), ("All Files", "*.*")))
        if filename:
            with open(filename, "r", encoding="utf-8") as f:
                self.signalements = sigparser.parse(f.read())
            if self.signalements:
                self.refresh(scroll="up")
                self.statusbar.set(
                    "Nouvelle session depuis '{}', {} signalements importés.".format(filename, len(self.signalements))
                )

    def new_clipboard(self):
        self.signalements = sigparser.parse(pyperclip.paste())
        if self.signalements:
            self.refresh(scroll="up")
            self.statusbar.set(
                "Nouvelle session depuis le presse-papiers, {} signalements importés.".format(len(self.signalements))
            )

    def append_file(self):
        filename = fdialog.askopenfilename(filetypes=(("Text Files", "*.txt"), ("All Files", "*.*")))
        if filename:
            with open(filename, "r", encoding="utf-8") as f:
                signalements = sigparser.parse(f.read())
            if signalements:
                self.signalements.extend(signalements)
                self.refresh(scroll="down")
                self.statusbar.set(
                    "{} signalements ajoutés à la session courante depuis '{}'.".format(len(signalements), filename)
                )

    def append_clipboard(self):
        signalements = sigparser.parse(pyperclip.paste())
        if signalements:
            self.signalements.extend(signalements)
            self.refresh(scroll="down")
            self.statusbar.set(
                "{} signalements ajoutés à la session courante depuis le presse-papiers.".format(len(signalements))
            )

    def generate_contact_message(self):
        sig = self.tree_sig.get_selected_sigs()[0]
        template = "\n".join(self.contact["message"])
        message = template.format(**sig.__dict__)
        pyperclip.copy(message)
        self.statusbar.set("MP copié dans le presse-papiers.")

    def archive_selection(self):
        indexes = self.tree_sig.selection_indexes()
        if utils.validate_indexes(indexes):
            archived = []
            msg = "Êtes-vous sûr de vouloir archiver {} signalements ?".format(len(indexes))
            if mbox.askokcancel("Archiver sélection", msg, parent=self):
                for i in indexes:
                    sig = self.signalements[i]
                    if "todo" in sig.statut:
                        msg = "{} signalements sur {} ont été archivés car il en reste un non traité :\n{}"
                        mbox.showwarning("Archivage incomplet", msg.format(i, indexes[-1] + 1, sig.sigmdm()),
                                         parent=self)
                        break
                    elif self.archives.archive_sig(sig):
                        archived.append(sig)
                    else:
                        break
                if archived:
                    self.signalements = [sig for sig in self.signalements if sig not in archived]
                    self.refresh(archives=True, scroll="up")
                    self.statusbar.set("{} signalements archivés.".format(len(archived)))
        else:
            msg = ("Votre sélection doit être d'un seul bloc (pas de trous) et doit commencer par le premier " +
                   "signalement afin de conserver l'ordre des archives.")
            mbox.showerror("Mauvais archivage", msg)

    def export_save(self, path=None):
        if path:
            filename = path
        else:
            filename = fdialog.asksaveasfilename(initialdir="saves", initialfile="session", defaultextension=".sig")
        if filename:
            logging.info("Exporting '{}'".format(filename))
            dicts = []
            for i, sig in enumerate(self.signalements):
                d = sig.ordered_dict()
                d.update({"#": i + 1})
                d.move_to_end("#", last=False)
                dicts.append(d)
            with open(filename, "w", encoding="utf-8") as f:
                f.write(json.dumps(dicts, indent=4, ensure_ascii=False))
            self.statusbar.set("{} signalements exportés dans '{}'.".format(len(self.signalements), filename))

    def import_save(self, path=None):
        if path:
            filename = path
        else:
            filename = fdialog.askopenfilename(initialdir="saves",
                                               filetypes=(("Sig Files", "*.sig"), ("All Files", "*.*")))
        if filename:
            logging.info("Importing '{}'".format(filename))
            self.session_path = filename
            with open(filename, "r", encoding="utf-8") as f:
                dicts = json.load(f)
            del self.signalements[:]
            for d in dicts:
                self.signalements.append(signalement.Signalement.from_dict(d))
            self.refresh(scroll="down")
            self.statusbar.set("{} signalements importés depuis '{}'.".format(len(self.signalements), filename))

    def focus_searchbar(self):
        self.searchbar.focus()
        self.searchbar.select_range(0, "end")

    def refresh(self, archives=False, scroll=None):
        logging.debug("Refreshing {} sigs".format(len(self.signalements)))
        self.tree_sig.signalements = self.signalements
        self.tree_sig.refresh()
        if archives:
            self.archives.refresh()
        self.tree_sig.search(debounced=True)
        if scroll == "down":
            self.tree_sig.scroll_down()
        elif scroll == "up":
            self.tree_sig.scroll_up()

    def clear_focus(self):
        self.tree_sig.deselect_all()
        self.main_frame.focus_force()

    def quit(self):
        logging.info("Exiting {}\n".format(__appname__))
        logging.shutdown()
        raise SystemExit


if __name__ == "__main__":
    log_level = utils.init_logging()
    logging.info("Starting {} {} [log_level={}]".format(__appname__, __version__, log_level))
    logging.info(
        "Running on {} {} (Python {})".format(platform.system(), platform.version(), platform.python_version()))

    app_title = "{} {}".format(__appname__, __version__)
    message = ""
    session = "saves/session.sig"
    arch_dir = "archives/"
    arch_pattern = "archives_{0}{0}{0}{0}.txt".format("[0-9]")
    app = RespoTool(app_title, session_path=session, archives_dir=arch_dir, archives_pattern=arch_pattern,
                    warning_message=message)
    app.mainloop()
