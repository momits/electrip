#!/usr/bin/env python
# -*- coding: utf-8 -*-

from gi.repository import Gtk, GObject
import subprocess as sub
import os
import mmap
from itertools import takewhile
from shutil import copy, Error

LIMITS_PATH = "/etc/security/limits.conf"
LIMITS_LINE = "srcpd    -    rtprio    99"
# TODO: check if "/etc/pam.d/sudo" should also be included
PAM_PATHS = ["/etc/pam.d/su", "/etc/pam.d/login"]
PAM_LINE = "session    required   pam_limits.so"

class SrcpdAssistant(Gtk.Assistant):
    def __init__(self):
        Gtk.Assistant.__init__(self)
        self.connect("cancel", self.quit)
        self.connect("delete-event", self.quit)
        self.connect("close", self.quit)
        self.set_title("Den SRCP-Server 'srcpd' einrichten")
        self.pages = [(WelcomePage(), Gtk.AssistantPageType.INTRO, "Willkommen!"),
                      (RealtimePage(self), Gtk.AssistantPageType.CONTENT, "Realtime-Rechte"),
                      (WebConfigEditorPage(self), Gtk.AssistantPageType.CONTENT, "Konfigurationsdatei"),
                      (SummaryPage(), Gtk.AssistantPageType.SUMMARY, "Glückwunsch!")]
        for page, page_type, page_title in self.pages:
            self.append_page(page)
            self.set_page_title(page, page_title)
            self.set_page_type(page, page_type)
        self.set_page_complete(self.pages[0][0], True)
        self.show_all()
        
    def quit(self, *args):
        Gtk.main_quit()
        
class MarkupLabel(Gtk.Label):
    def __init__(self, markup):
        Gtk.Label.__init__(self)
        self.set_halign(Gtk.Align.START)
        self.set_markup(markup)
        self.set_line_wrap(True)
        
class WelcomePage(MarkupLabel):
    def __init__(self):
        MarkupLabel.__init__(self,
                             "Herzlich Willkommen!\nDieser Dialog führt Sie durch die Konfiguration des srcpd-Servers auf Ubuntu.\n" + \
                             "Der srcpd muss bereits installiert sein." + \
                             "Klicken Sie auf '<b>Fortsetzen</b>' um die Einrichtung des srcpd zu beginnen.")
        
class RealtimePage(Gtk.Grid):
    def __init__(self, assistant):
        Gtk.Grid.__init__(self)
        self.assistant = assistant
        self.set_orientation(Gtk.Orientation.VERTICAL)
        self.set_row_spacing(5)
        self.add(MarkupLabel("Der srcpd benötigt <b>spezielle Rechte</b> um schnell auf die serielle Schnittstelle zugreifen zu können.\n" + \
                             "Dazu sollte\n" + \
                             "<b>1. </b>ein <b>neuer Benutzer namens \"srcpd\"</b> im System angelegt werden und\n" + \
                             "<b>2. </b>in die Datei \"<b>/etc/security/limits.conf</b>\" eingetragen werden.\n" + \
                             "<b>3. PAM</b> (Pluggable Authentication Module) so konfiguriert werden, dass Ihr System die Datei \"limits.conf\" auch beachtet."))
        button = Gtk.Button("Realtime-Rechte einrichten")
        button.connect("clicked", self.set_realtime_privileges)
        button.set_halign(Gtk.Align.CENTER)
        button.set_valign(Gtk.Align.CENTER)
        self.add(button)
        self.error_label = Gtk.Label()
        self.error_label.set_halign(Gtk.Align.START)
        self.add(self.error_label)
        
    def set_realtime_privileges(self, button):
        error_text = ""
        button.set_sensitive(False)
        try:
            sub.check_call(["addgroup", "--system", "srcpd"])
            sub.check_call(["adduser", "--system", "--no-create-home", "--ingroup", "srcpd", "srcpd"])
        except sub.CalledProcessError as error:
            error_text += "<b>1. </b>Konnte Benutzer nicht hinzufügen, Fehlercode: ", error.returncode, "\n"
            button.set_sensitive(True)
        else:
            error_text += "<b>1. </b>Benutzer 'srcpd' wurde hinzugefügt (oder ist bereits vorhanden)\n"
            
            f, mapped_file = self.create_mapped_file(LIMITS_PATH)
            if mapped_file.find("srcpd") == -1:
                self.append_line_to_mapped_file(mapped_file, LIMITS_LINE)
                mapped_file.close()
                f.close()
                error_text += "<b>2. </b>srcpd wurde in limits.conf eingetragen\n"
                
            else:
                error_text += "<b>2. </b>srcpd ist bereits in limits.conf eingetragen\n"
                
            pam_changes_needed = False
            for pam_path in PAM_PATHS:
                f, mapped_file = self.create_mapped_file(pam_path)
                pos = mapped_file.find("pam_limits.so")
                if pos == -1:
                    self.append_line_to_mapped_file(mapped_file, PAM_LINE)
                    mapped_file.close()
                    f.close()
                    pam_changes_needed = True
                else:
                    # gives us the byte-pos for all the lines up to the searched word:
                    byte_positions = list(takewhile(lambda x: x <= pos, self.count_bytes(f)))
                    # go to start-byte of the searched line
                    mapped_file.seek(byte_positions[-1])
                    line = mapped_file.readline()
                    if line[0] == "#":
                        mapped_file.seek(byte_positions[-1])
                        mapped_file.write(PAM_LINE)
                        # calculate the start and end position for the rest of the old line we want to cut away
                        start = mapped_file.tell()
                        end = start + len(mapped_file.readline()) - 1
                        # remove the rest of the old line
                        self.remove_from_mapped_file(mapped_file, start, end)
                        pam_changes_needed = True
                    
            if pam_changes_needed:
                error_text += "<b>3. </b>PAM wurde konfiguriert\n"
            else:
                error_text += "<b>3. </b>PAM war bereits korrekt konfiguriert\n"
            button.set_label("Rechte wurden erfolgreich eingerichtet!")
            self.assistant.set_page_complete(self, True)
        self.error_label.set_markup(error_text)
        
    def create_mapped_file(self, path):
        f = open(path, "r+")
        return f, mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_WRITE)
    
    def append_line_to_mapped_file(self, mapped_file, new_line):
        mapped_file.seek(0, os.SEEK_END)
        mapped_file.resize(len(mapped_file) + len(new_line))
        mapped_file.write(new_line)
        
    def remove_from_mapped_file(self, mapped_file, start, end):
        file_length = len(mapped_file)
        cut_length = end - start
        new_length = file_length - cut_length
        mapped_file.move(start, end, file_length - end)
        mapped_file.resize(new_length)
        
    def count_bytes(self, iterable):
        bytes = 0
        for item in iterable:
            bytes += len(item)
            yield bytes

class WebConfigEditorPage(Gtk.Grid):
    def __init__(self, assistant):
        self.assistant = assistant
        
        Gtk.Grid.__init__(self)
        self.set_orientation(Gtk.Orientation.VERTICAL)
        self.set_row_spacing(5)
        self.add(MarkupLabel("Als Nächstes muss die <b>Konfigurationsdatei \"/etc/srcpd.conf\"</b> erstellt werden.\n" + \
                             "Gehen Sie dazu auf den \"<b>Web Config Generator</b> (Rechtsklick->Kopieren):\""))
        label = MarkupLabel("<span fgcolor='#0080FF'>srcpd.sourceforge.net/srcpd/cfg/index.html</span>")
        label.set_selectable(True)
        label.set_margin_top(5)
        label.set_margin_bottom(5)
        self.add(label)
        self.add(MarkupLabel("<b>1. Befolgen Sie die Anweisungen der Webanwendung</b> (leider auf Englisch).\n" + \
                             "<b>2. Speichern</b> Sie dann die erzeugte XML-Datei in ein beliebiges Verzeichnis (unter Firefox: Rechtsklick->Seite speichern unter...)\n" + \
                             "<b>3. Geben Sie hier die gespeicherte Datei an</b>, damit sie an die korrekte Stelle (\"/etc\") kopiert wird:"))
        file_button = Gtk.FileChooserButton()
        file_filter = Gtk.FileFilter()
        file_filter.set_name("XML-Textdateien")
        file_filter.add_mime_type("application/xml")
        file_button.add_filter(file_filter)
        file_button.connect("file-set", self.show_copy_confirmation)
        self.add(file_button)
        
        self.confirm_label = MarkupLabel("<i>Keine Datei zum Kopieren gewählt</i>")
        self.confirm_label.set_sensitive(False)
        self.add(self.confirm_label)
        self.copy_button = Gtk.Button("Datei kopieren")
        self.copy_button.connect("clicked", self.copy_file_to_etc)
        self.copy_button.set_sensitive(False)
        self.add(self.copy_button)
        
    def show_copy_confirmation(self, file_button):
        self.file_path = file_button.get_filename()
        self.confirm_label.set_text("Soll die Datei \"" + self.file_path + "\" nach \"/etc\" kopiert werden?")
        self.confirm_label.set_sensitive(True)
        self.copy_button.set_sensitive(True)
        
    def copy_file_to_etc(self, button):
        try:
            copy(self.file_path, "/etc")
        except Error:
            self.confirm_label.set_text("Fehler beim Kopieren: Quelldatei liegt bereits in \"/etc\"!")
        else:
            self.confirm_label.set_text("Datei wurde erfolgreich kopiert!")
            self.confirm_label.set_sensitive(False)
            self.copy_button.set_sensitive(False)
            self.assistant.set_page_complete(self, True)

class SummaryPage(MarkupLabel):
    def __init__(self):
        MarkupLabel.__init__(self, "<b>Herzlichen Glückwunsch!</b>\nDer srcpd wurde erfolgreich eingerichtet und kann jetzt verwendet werden.")

if __name__ == "__main__":
    if os.getuid() == 0: # if user-id=0 we are root (which is needed for all operations)
        assistant = SrcpdAssistant()
        GObject.threads_init()
        Gtk.main()
    else:
        sub.call(["gksudo", "python srcpd_setup_assistant.py"])
