# -*- coding: utf-8 -*-

# pylint: disable=W0613
# pylint: disable=R0904
# pylint: disable=R0921
# pylint: disable=R0201

"""SpiceGUI Application module."""

# SpiceGUI
# Copyright (C) 2014-2015 Rafael Bailón-Ruiz <rafaelbailon@ieee.org>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import print_function

import os
import os.path
import webbrowser

from gi.repository import Gio, Gtk

import config
import gui
import preferences_gui


class SpiceGUI(Gtk.Application):
    """SpiceGUI Application."""

    def __init__(self):
        """Inits SpiceGUI Application."""
        Gtk.Application.__init__(self,
                                 application_id=config.APPLICATION_ID,
                                 flags=Gio.ApplicationFlags.HANDLES_OPEN)
                                 
        Gtk.Window.set_default_icon_name("spicegui")

        self.builder = Gtk.Builder()
        self.builder.set_translation_domain(config.DOMAIN)

        self.connect("activate", self.on_activate)
        self.connect("startup", self.on_startup)
        self.connect("open", self.on_open)

        self.file_args = []

    def on_startup(self, app):
        """Initializes application AppMenu.

        ``startup`` signal handler.

        Args:
            app: Appliction.
        """
        Gtk.Application.do_startup(self)

        self.builder.add_from_file(os.path.join(os.path.dirname(__file__), "data", "menu.ui"))

        appmenu = self.builder.get_object('appmenu')
        self.set_app_menu(appmenu)

        new_action = Gio.SimpleAction.new("new", None)
        new_action.connect("activate", self.on_new_action)
        self.add_action(new_action)

        preferences_action = Gio.SimpleAction.new("preferences", None)
        preferences_action.connect("activate", self.on_preferences_action)
        self.add_action(preferences_action)

        help_action = Gio.SimpleAction.new("help", None)
        help_action.connect("activate", self.on_help_action)
        self.add_action(help_action)

        about_action = Gio.SimpleAction.new("about", None)
        about_action.connect("activate", self.on_about_action)
        self.add_action(about_action)

        quit_action = Gio.SimpleAction.new("quit", None)
        quit_action.connect("activate", self.on_quit_action)
        self.add_action(quit_action)

        self.set_accels_for_action("win.save", ["<Primary>S"]);

    def on_activate(self, app):
        """Starts SpiceGUI.

        ``activate`` signal handler.

        Args:
            app: Appliction.
        """
        window = gui.MainWindow()
        app.add_window(window)
        window.show_all()

    def on_open(self, app, files, hint, user_data):
        """Opens circuit file from command line.

        ``open`` signal handler.

        Args:
            app: Appliction.
            files: An array of Gio.Files.
            hint: A hint provided by the calling instance.
            user_data: User-defined data.
        """
        for _file in files:
            window = gui.MainWindow(_file.get_path())
            app.add_window(window)
            window.show_all()

    def on_new_action(self, action, parameter):
        """Opens new SpiceGUI window.

        ``new`` action ``activate`` signal handler.

        Args:
            action: GAction.
            parameter: The parameter to the activation.
        """
        self.activate()

    def on_preferences_action(self, action, parameter):
        """Shows Preferences window.

        ``preferences`` action ``activate`` signal handler.

        Args:
            action: GAction.
            parameter: The parameter to the activation.
        """
        preferences_gui.Preferences(self.get_active_window())

    def on_help_action(self, action, parameter):
        """Shows Help web page.

        ``help`` action ``activate`` signal handler.

        Args:
            action: GAction.
            parameter: The parameter to the activation.
        """
        webbrowser.open(config.HELP_URL)

    def on_about_action(self, action, parameter):
        """Shows About dialog.

        ``about`` action ``activate`` signal handler.

        Args:
            action: GAction.
            parameter: The parameter to the activation.
        """
        aboutdialog = Gtk.AboutDialog()
        aboutdialog.connect("response", lambda w, r: aboutdialog.destroy())
        aboutdialog.set_title(_("About SpiceGUI"))
        aboutdialog.set_program_name(config.PROGRAM_NAME)
        aboutdialog.set_version(config.VERSION)
        aboutdialog.set_comments(_("Graphical user interface for circuit simulation using ngspice."))
        aboutdialog.set_copyright("Copyright © 2014-2015 Rafael Bailón-Ruiz")
        aboutdialog.set_logo_icon_name(config.PROGRAM_NAME_LOWER)
        aboutdialog.set_website(config.PROGRAM_WEBSITE)
        aboutdialog.set_license_type(Gtk.License.GPL_3_0)

        authors = ["Rafael Bailón-Ruiz <rafaelbailon@ieee.org>"]
        aboutdialog.set_authors(authors)

        translators = _("translator-credits")
        aboutdialog.set_translator_credits(translators)

        aboutdialog.show()

    def on_quit_action(self, action, parameter):
        """Exits SpiceGUI application.

        ``quit`` action ``activate`` signal handler.

        Args:
            action: GAction.
            parameter: The parameter to the activation.
        """
        self.quit()
