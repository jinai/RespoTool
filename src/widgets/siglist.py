# -*- coding: utf-8 -*-
# !python3

import json
import logging
import winsound

import pyperclip

from widgets.treelist import Treelist
from widgets.popup import Popup
from widgets.editstatus import EditStatusDialog
from signalement import Signalement

logger = logging.getLogger(__name__)


class Siglist(Treelist):
    def __init__(self, master, signalements, respomap, archives, *args, **kwargs):
        Treelist.__init__(self, master, *args, **kwargs)
        self.signalements = signalements
        self.respomap = respomap
        self._keys = {
            0: lambda x: 0,
            1: lambda x: x.datetime(),
            2: lambda x: x.auteur.lower(),
            3: lambda x: x.code,
            4: lambda x: x.flag.lower(),
            5: lambda x: x.desc.lower(),
            6: lambda x: x.statut.lower(),
            7: lambda x: str(x.respo)
        }
        self._entry_edit = None
        self.archives = archives
        self.last_popup = None
        self.tree.bind('<Double-1>', self.on_doubleclick)
        self.tree.bind('<Return>', self.on_enter)
        self.tree.bind('<Control-c>', self.copy)
        self.tree.bind('<space>', self.on_space)
        self.tree.bind('<FocusOut>', self.remove_popup)
        self.tree.bind('<<TreeviewSelect>>', self.remove_popup)
        self.update_tags()
        self.update_templates()

    def update_tags(self):
        with open("resources/tags.json", 'r', encoding='utf-8') as f:
            self.tags = json.load(f)
        for key in self.tags:
            self.tree.tag_configure(key, background=self.tags[key])

    def update_templates(self):
        with open("resources/archives_templates.json", 'r', encoding='utf-8') as f:
            self.archives_templates = json.load(f)

    def insert(self, values, update=True, tags=None):
        tags = []
        for key in self.tags:
            if key in values[-2]:
                tags.append(key)
        super().insert(values, update, tags)

    def delete(self):
        if self.tree.selection():
            for item in self.tree.selection():
                values = self.tree.item(item)['values']
                values[0] = str(values[0])  # Treeviews force str to int if it's a digit
                values[-1] = [respo.strip() for respo in values[-1].split(",")] if values[-1] else []
                sig = Signalement(*values[1:])
                self.signalements.remove(sig)
                logger.debug("Deleting {}".format(sig))
            index = super().delete()
            self.refresh()
            if self._search_key.get() != '':
                self.search()
            self.focus_index(index)

    def selection_indexes(self):
        indexes = []
        selection = self.tree.selection()
        for item in selection:
            indexes.append(int(self.tree.item(item)['values'][0]) - 1)
        return indexes

    def sort(self, col, descending):
        if self.sortable:
            index = self.headers.index(col)
            if index == 0:
                self.signalements.reverse()
            else:
                self.signalements.sort(reverse=descending, key=self._keys[index])
            super().sort(col, descending)

    def search(self, key=None):
        key = key.strip() if key is not None else self._search_key.get().strip()
        if key == '':
            self.refresh()
        else:
            super().search(key)

    def on_doubleclick(self, event):
        if self.tree.identify_region(event.x, event.y) == "cell":
            # Clipboard
            item = self.tree.identify("item", event.x, event.y)
            column = int(self.tree.identify("column", event.x, event.y)[1:]) - 1
            value = str(self.tree.item(item)['values'][column])
            pyperclip.copy(value)
            # Popup
            x, y = self.master.winfo_pointerx(), self.master.winfo_pointery()
            msg = value if len(value) <= 20 else value[:20] + "..."
            Popup('"{}" copié dans le presse-papiers'.format(msg), x, y, delay=50, txt_color="white",
                  bg_color="#111111")

    def on_enter(self, event):
        select = self.tree.selection()
        if select:
            if self.respomap.get() == '':
                winsound.PlaySound('SystemHand', winsound.SND_ASYNC)
                x, y = self.master.winfo_rootx(), self.master.winfo_rooty()
                Popup("<- Qui es-tu ? ^_^", x, y, offset=(220, 61), delay=50, txt_color='white', bg_color='#111111')
                self.master.master.dropdown_respo.event_generate("<Button-1>")  # Hacky access the combobox of the main app
                return
            item = select[0]
            item_index = self.tree.get_children().index(item)
            values = self.tree.item(item)['values']
            values[0] = str(values[0])  # Treeviews force str to int if it's a digit
            data_index = self._data.index(values)
            dialog = EditStatusDialog(self, "Éditer statut #{} : {}".format(values[0], values[3]), values[-2])
            new_statut = dialog.result
            if new_statut is not None and new_statut != values[-2]:
                values[-1] = [respo.strip() for respo in values[-1].split(",")] if values[-1] else []
                sig = Signalement(*values[1:])
                sig_index = self.signalements.index(sig)
                respo = self.respomap.get()
                if respo != '' and respo not in sig.respo:
                    sig.respo.append(respo)
                if "/reset" in new_statut.lower():
                    sig.respo = []
                else:
                    sig.statut = new_statut
                new_values = list(sig.fields())
                new_values.insert(0, values[0])
                new_values[-1] = ", ".join(new_values[-1])
                self._data[data_index] = new_values
                self.signalements[sig_index] = sig
                self.search('')  # Todo : this shouldn't reset the search
                self.focus_index(item_index)
            else:
                self.focus_item(item)

    def copy(self, event):
        selection = self.tree.selection()
        if len(selection) == 1:
            item = selection[0]
            load = "/load "
            load += self.tree.item(item)['values'][3]
            pyperclip.copy(load)
            try:
                x, y = self.tree.bbox(item, "code")[:2]
                x = x + self.winfo_rootx()
                y = y + self.winfo_rooty() - 21
                Popup('"{}" copié dans le presse-papiers'.format(load), x, y, delay=50, offset=(0, 0),
                      txt_color="white",
                      bg_color="#111111")
            except ValueError:
                pass

    def on_space(self, event):
        selection = self.tree.selection()
        if len(selection) == 1:
            item = selection[0]
            code = self.tree.item(item)['values'][3]
            match_archives = self.archives.filter_sigs("code", code)
            match_session = self.archives.filter_sigs("code", code, source=self.signalements)
            if len(match_archives) != 0 or len(match_session) > 1:
                self.remove_popup()
                text = ""
                if len(match_archives) != 0:
                    text += self.archives_templates["archives_msg"]
                    text += "\n    ".join(
                        [''] + [self.archives_templates["archives"].format(**s.__dict__) for s in match_archives])
                if len(match_session) > 1:
                    if text:
                        text += "\n"
                    text += self.archives_templates["session_msg"]
                    text += "\n    ".join(
                        [''] + [self.archives_templates["session"].format(**s.__dict__) for s in match_session])
                x, y = self.tree.bbox(item, "code")[:2]
                x = x + self.winfo_rootx()
                y = y + self.winfo_rooty() + 20
                self.last_popup = Popup(text, x, y, delay=50, offset=(0, 0), persistent=True, max_alpha=0.90,
                                        txt_color="white", bg_color="#111111")

    def remove_popup(self, *args):
        if self.last_popup:
            self.last_popup.destroy()

    def populate(self):
        for i, sig in enumerate(self.signalements):
            f = list(sig.fields())
            f[-1] = ", ".join(f[-1])
            self.insert(f)

    def refresh(self):
        self.clear()
        self.populate()
        self.update_tags()
        self.update_templates()
