# -*- coding: utf-8 -*-
#
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

import os.path

from gi.repository import Gtk, Gdk, Gio, GtkSource, Pango
from matplotlib.backends.backend_gtk3cairo import FigureCanvasGTK3Cairo as FigureCanvas

import config
import console_gui
import ngspice_simulation
import running_dialog
import add_simulation_gui


class MainWindow(Gtk.ApplicationWindow):

    def __init__(self, file_path=None):
        Gtk.Window.__init__(self)
        self.set_default_size(900, 600)
        self.set_icon_name(config.PROGRAM_NAME_LOWER)

        self.settings = Gio.Settings.new(config.GSETTINGS_BASE_KEY)

        self.circuit = None
        self.netlist_file_path = None
        self.file_monitor = None
        self.raw_data_window = console_gui.ConsoleOutputWindow(_("Simulation output"))
        self.execution_log_window = console_gui.ConsoleOutputWindow(_("Execution log"))
        self._create_menu_models()

        ##########
        #headerbar
        self.hb = Gtk.HeaderBar()
        self.hb.props.show_close_button = True

        if config.csd_are_supported() == True:
            self.set_titlebar(self.hb)
        else: #disable headerbar as titlebar if not supported
            self.no_csd_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            self.no_csd_box.pack_start(self.hb, False, False, 0)
            self.hb.props.show_close_button = False
            self.add(self.no_csd_box)

        ## Right side of headerbar
        self.hb_rbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

        self._add_insert_button()
        self._add_simulate_button()
        self._add_gear_button()

        self.hb.pack_end(self.hb_rbox)

        ## Left side of headerbar
        self._add_arrow_buttons()
        self._add_load_button()

        ########
        #Content
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        self.stack.set_transition_duration(500)

        ## Overview stack
        self.overview_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.source_view = None
        self._open_state("new")

        self.infobar = None
        self.stack.add_titled(self.overview_box, "overview", _("Circuit"))

        ## Simulation stack
        self.simulation_box = Gtk.Box()
        self.canvas = Gtk.DrawingArea()
        self.simulation_box.pack_start(self.canvas, True, True, 0)
        self.stack.add_titled(self.simulation_box, "simulation", _("Simulation"))

        if config.csd_are_supported() == True:
            self.add(self.stack)
        else: #disable headerbar as titlebar if not supported
            self.no_csd_box.pack_end(self.stack, True, True, 0)

        self.overview_view()
        self.forward_button.props.sensitive = False  # HACK: self._open_state("new") sets it to
                                                     # False but self.overview_view() sets it to
                                                     # True. This line fixes the incongruence.

        self.connect_after('destroy', self._on_destroy)

        if file_path is not None:
            self.load_file(file_path)

    def _open_state(self, state="opened"):
        """
        show sourceview state="opened" or suggest opening a file state="new"
        """
        if state == "opened":
            self.overview_view()
            self.forward_button.props.sensitive = False  # Don go forward until having some simulations
            for child in self.overview_box.get_children():
                self.overview_box.remove(child)
            self.source_scrolled = Gtk.ScrolledWindow(None, None)
            self.source_scrolled.set_hexpand(True)
            self.source_scrolled.set_vexpand(True)

            self.source_buffer = GtkSource.Buffer()
            self.source_buffer.connect("modified-changed", self.on_source_buffer_modified_changed)
            self.source_buffer.set_highlight_syntax(True)
            self.source_buffer.set_language(GtkSource.LanguageManager.get_default().get_language("spice-netlist"))
            self.sourceview = GtkSource.View()
            self.settings.bind('show-line-numbers', self.sourceview, 'show-line-numbers', Gio.SettingsBindFlags.DEFAULT)
            self.settings.bind('highlight-current-line', self.sourceview, 'highlight-current-line', Gio.SettingsBindFlags.DEFAULT)
            font_desc = Pango.FontDescription('monospace')
            if font_desc:
                self.sourceview.modify_font(font_desc)
            self.sourceview.set_buffer(self.source_buffer)
            self.sourceview.set_show_line_numbers(True)
            self.source_scrolled.add(self.sourceview)
            self.overview_box.pack_end(self.source_scrolled, True, True, 0)
            self.overview_box.show_all()
            self.insert_button.props.sensitive = True
            self.simulate_button.props.sensitive = True
            self.lookup_action("save").props.enabled = True
        elif state == "new":
            if self.source_view is not None:
                self.overview_box.remove(self.source_scrolled)
                self.source_view = None
            else:
                self.emptyGrid = Gtk.Grid(orientation=Gtk.Orientation.HORIZONTAL, hexpand=True, vexpand=True, halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER, column_spacing=12, margin=30)
                self.overview_box.add(self.emptyGrid);
                emptyPageImage = Gtk.Image(icon_name='document-open-symbolic', icon_size=Gtk.IconSize.DIALOG)
                emptyPageImage.get_style_context().add_class('dim-label')
                self.emptyGrid.add(emptyPageImage)
                emptyPageDirections = Gtk.Label(label=_("Use the <b>Open</b> button to load a circuit"), use_markup=True, max_width_chars=30, halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER )
                emptyPageDirections.get_style_context().add_class('dim-label');
                self.emptyGrid.add(emptyPageDirections);
                self.emptyGrid.show_all();
                self.overview_box.pack_end(self.emptyGrid, True, True, 0)
                self.insert_button.props.sensitive = False
                self.simulate_button.props.sensitive = False
                self.forward_button.props.sensitive = False # TODO: let see why this is not effective...
                self.lookup_action("save").props.enabled = False

    def _create_menu_models(self):
        # gear_menu overview xml #
        ## Create menu model
        builder = Gtk.Builder()
        builder.set_translation_domain(config.DOMAIN)
        builder.add_from_file(os.path.join(os.path.dirname(__file__), "data", "menu.ui"))
        self.gearmenu_overview = builder.get_object('gearmenu-overview')

        ## Bind actions
        save_action = Gio.SimpleAction.new("save", None)
        save_action.connect("activate", self.save_cb)
        self.add_action(save_action)

        close_action = Gio.SimpleAction.new("close", None)
        close_action.connect("activate", self.close_cb)
        self.add_action(close_action)

        # gear_menu simulation xml #
        ## Create menu model
        self.gearmenu_simulation = builder.get_object('gearmenu-simulation')

        ## Bind actions
        save_plot_action = Gio.SimpleAction.new("save-plot", None)
        save_plot_action.connect("activate", self.save_plot_cb)
        self.add_action(save_plot_action)

        save_data_action = Gio.SimpleAction.new("save-data", None)
        save_data_action.connect("activate", self.save_data_cb)
        self.add_action(save_data_action)

        simulation_log_action = Gio.SimpleAction.new("simulation-output", None)
        simulation_log_action.connect("activate", self.simulation_output_action_cb)
        self.add_action(simulation_log_action)

        # insert_menu_xml #
        ## Create menu model
        self.insertmenu = builder.get_object('insertmenu')

        ## Bind actions
        insert_simulation_action = Gio.SimpleAction.new("insert-simulation", None)
        insert_simulation_action.connect("activate", self.insert_simulation_action)
        self.add_action(insert_simulation_action)

        insert_print_action = Gio.SimpleAction.new("insert-print", None)
        insert_print_action.connect("activate", self.insert_print_cb)
        self.add_action(insert_print_action)

        insert_model_action = Gio.SimpleAction.new("insert-model", None)
        insert_model_action.connect("activate", self.insert_model_cb)
        self.add_action(insert_model_action)

        insert_lib_action = Gio.SimpleAction.new("insert-lib", None)
        insert_lib_action.connect("activate", self.insert_lib_cb)
        self.add_action(insert_lib_action)

        insert_include_action = Gio.SimpleAction.new("insert-include", None)
        insert_include_action.connect("activate", self.insert_include_cb)
        self.add_action(insert_include_action)

    def save_cb(self, action, parameters):
        self.save_netlist_file()

    def save_plot_cb(self, action, parameters):
        dialog = Gtk.FileChooserDialog(_("Save plot"), self, Gtk.FileChooserAction.SAVE,
                                       (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_SAVE, Gtk.ResponseType.OK))

        png_filter = Gtk.FileFilter()
        png_filter.set_name(_("Portable Network Graphics"))
        png_filter.add_mime_type("image/png")
        dialog.add_filter(png_filter)

        svg_filter = Gtk.FileFilter()
        svg_filter.set_name(_("Scalable Vector Graphics"))
        svg_filter.add_mime_type("image/svg+xml")
        dialog.add_filter(svg_filter)

        dialog.set_current_name(self.circuit_title + " - " + self.simulation_output.analysis)

        response = dialog.run()
        dialog.set_filter(png_filter)
        if response == Gtk.ResponseType.OK:
            file_name = dialog.get_filename()
            dialog.destroy()
            if file_name.split(".")[-1] == "png":
                self.figure.savefig(file_name, transparent=True, dpi=None, format="png")
            elif file_name.split(".")[-1] == "svg":
                self.figure.savefig(file_name, transparent=True, dpi=None, format="svg")
            else:
                self.figure.savefig(file_name+".png", transparent=True, dpi=None, format="png")
                #TODO: Fix this!
#                selected_filter = dialog.get_filter()
#                if selected_filter is png_filter:
#                    self.figure.savefig(file_name+".png", transparent=True, dpi=None, format="png")
#                elif selected_filter is png_filter:
#                    self.figure.savefig(file_name+".png", transparent=True, dpi=None, format="png")
        else:
            dialog.destroy()

    def save_data_cb(self, action, parameters):
        dialog = Gtk.FileChooserDialog(_("Save simulation data"), self, Gtk.FileChooserAction.SAVE,
                                       (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_SAVE, Gtk.ResponseType.OK))

        csv_filter = Gtk.FileFilter()
        csv_filter.set_name(_("Comma-separated values"))
        csv_filter.add_mime_type("text/csv")
        dialog.add_filter(csv_filter)

        dialog.set_current_name(self.circuit_title + " - " + self.simulation_output.analysis)

        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            file_name = dialog.get_filename()
            dialog.destroy()
            if file_name.split(".")[-1] != "csv":
                file_name += ".csv"
            self.simulation_output.save_csv(file_name)
        else:
            dialog.destroy()

    def simulation_output_action_cb(self, action, parameters):
        if self.raw_data_window is None:
            self.raw_data_window = console_gui.ConsoleOutputWindow(_("Simulation output"))
        self.raw_data_window.show_all()

    def close_cb(self, action, parameters):
        self.destroy()
    
    def insert_simulation_action(self, action, parameters):
        dialog = add_simulation_gui.AddSimulation(self,[])
        
        response = dialog.run()
        
        if response == Gtk.ResponseType.OK:
            self.source_buffer.insert_at_cursor(dialog.statement)
            dialog.destroy()
        dialog.destroy()

    def insert_print_cb(self, action, parameters):
        self.source_buffer.insert_at_cursor(".print ")

    def insert_model_cb(self, action, parameters):
        self.source_buffer.insert_at_cursor(".model mname type (  )")

    def insert_lib_cb(self, action, parameters):
        self.source_buffer.insert_at_cursor(".lib filename libname")

    def insert_include_cb(self, action, parameters):
        self.source_buffer.insert_at_cursor(".include filename")

    def _add_back_button(self):
        self.back_button = Gtk.Button()
        self.back_button.add(Gtk.Arrow(Gtk.ArrowType.LEFT, Gtk.ShadowType.NONE))

        self.back_button.connect("clicked", self.on_back_button_clicked)
        self.hb.pack_start(self.back_button)
        self.back_button.props.visible = False

    def _add_gear_button(self):
        self.gear_button = Gtk.MenuButton()

        #Set content
        icon = Gio.ThemedIcon(name="emblem-system-symbolic")
        # Use open-menu-symbolic on Gtk+>=3.14
        if Gtk.check_version(3, 14, 0) is None:
            icon = Gio.ThemedIcon(name="open-menu-symbolic")
        image = Gtk.Image.new_from_gicon(icon, Gtk.IconSize.MENU)
        self.gear_button.add(image)

        # Use popover on Gtk+>=3.12
        if Gtk.check_version(3, 12, 0) is None:
            self.gear_button.set_use_popover(True)

        #Pack
        self.hb_rbox.pack_start(self.gear_button, False, False, 0)

    def _add_insert_button(self):
        self.insert_button = Gtk.MenuButton()

        #Set content
        icon = Gio.ThemedIcon(name="insert-text-symbolic")
        image = Gtk.Image.new_from_gicon(icon, Gtk.IconSize.MENU)
        self.insert_button.add(image)

        # Set menu model
        self.insert_button.props.menu_model = self.insertmenu

        # Use popover on Gtk+>=3.12
        if Gtk.check_version(3, 12, 0) is None:
            self.insert_button.set_use_popover(True)

        #Pack
        self.hb_rbox.pack_start(self.insert_button, False, False, 0)

    def _add_arrow_buttons(self):
        self.arrow_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        Gtk.StyleContext.add_class(self.arrow_box.get_style_context(), "linked")

        self.back_button = Gtk.Button()
        self.back_button.add(Gtk.Arrow(Gtk.ArrowType.LEFT, Gtk.ShadowType.NONE))
        self.arrow_box.add(self.back_button)
        self.back_button.connect("clicked", self.on_back_button_clicked)

        self.forward_button = Gtk.Button()
        self.forward_button.add(Gtk.Arrow(Gtk.ArrowType.RIGHT, Gtk.ShadowType.NONE))
        self.arrow_box.add(self.forward_button)
        self.forward_button.connect("clicked", self.on_forward_button_clicked)

        self.hb.pack_start(self.arrow_box)

    def _add_load_button(self):
        self.load_button = Gtk.Button()
        self.load_button.set_label(_("Open"))

        self.load_button.connect("clicked", self.on_button_open_clicked)
        self.hb.pack_start(self.load_button)

    def _add_simulate_button(self):
        self.simulate_button = Gtk.Button()
        icon = Gio.ThemedIcon(name="media-playback-start-symbolic")
        image = Gtk.Image.new_from_gicon(icon, Gtk.IconSize.MENU)
        self.simulate_button.add(image)

        self.simulate_button.connect("clicked", self.on_simulate_button_clicked)

        sim_accel = Gtk.AccelGroup()
        self.add_accel_group(sim_accel)
        self.simulate_button.add_accelerator("clicked", sim_accel, Gdk.KEY_F5, 0, Gtk.AccelFlags.VISIBLE);

        self.simulate_button.props.sensitive = False
        self.hb_rbox.pack_start(self.simulate_button, False, False, 0)

    def _update_canvas(self, figure):
        self.simulation_box.remove(self.canvas)
        self.canvas = FigureCanvas(figure)  # a Gtk.DrawingArea
        self.simulation_box.pack_start(self.canvas, True, True, 0)
        self.canvas.show()


    def set_error(self, title=None, message=None, message_type=Gtk.MessageType.ERROR, actions=None):
        '''set_error(self, title=None, message=None, message_type=Gtk.MessageType.ERROR, actions=None) -> None

        Sets and shows an information bar with actions as an option.

        params:
            actions -> (button_text, response_id, callback_function)
        '''
        if self.infobar is not None:
            self.infobar.close()
        self.infobar = InfoMessageBar()
        self.infobar.set_message_type(message_type)
        self.overview_box.pack_start(self.infobar, False, True, 0)

        if title is not None:
            self.infobar.message_title = title
        else:
            self.infobar.messsage_title = ""

        if message is not None:
            self.infobar.message_subtitle = message
        else:
            self.infobar.message_subtitle = ""

        if actions is not None:
            for action in actions:
                self.infobar.add_button(action[0], action[1])
                self.infobar.user_responses[action[1]] = action[2]

        self.infobar.show_all()

    def dismiss_error(self):
        if self.infobar is not None:
            self.infobar.props.visible = False
            self.infobar = None

    def simulation_view(self):
        self.stack.set_visible_child(self.simulation_box)
        self.back_button.props.sensitive = True
        self.forward_button.props.sensitive = False
        self.load_button.props.visible = False
        self.simulate_button.props.visible = False
        self.insert_button.props.visible = False
        self.gear_button.props.menu_model = self.gearmenu_simulation

    def overview_view(self):
        self.stack.set_visible_child(self.overview_box)
        self.back_button.props.sensitive = False
        self.forward_button.props.sensitive = True
        self.load_button.props.visible = True
        self.simulate_button.props.visible = True
        self.insert_button.props.visible = True
        self.gear_button.props.menu_model = self.gearmenu_overview

    def _on_destroy(self, data):
        self.destroy()

    def on_back_button_clicked(self, button):
        self.overview_view()

    def on_forward_button_clicked(self, button):
        self.simulation_view()

    def on_simulate_button_clicked(self, button):
        # Dismiss infobar messages (if they exists)
        self.dismiss_error()
        simulator = ngspice_simulation.NgspiceAsync()
        dialog = running_dialog.RunningDialog(self,simulator.end_event)
        try:
            # First, save changes on disk
            self.save_netlist_file()
            # Start simulation
            simulator.simulatefile(self.netlist_file_path)
            # Show dialog
            if dialog.run() == 1: # Not cancelled by the user
                if not simulator.errors:
                    self.simulation_output = ngspice_simulation.NgspiceOutput.parse_file(self.netlist_file_path + ".out")
                    self.figure = self.simulation_output.get_figure()
                    self._update_canvas(self.figure)
                    self.simulation_view()
                else:
                    errors_str = [str(x) for x in simulator.errors]
                    self.set_execution_log(self.netlist_file_path,"\n".join(errors_str))
                    self.set_error(title=_("Simulation failed."), actions=[(_("Execution log"), 1000, self.on_execution_log_clicked)])
            else:
                simulator.terminate()
            self.set_output_file_content(self.netlist_file_path + ".out")
        except Exception as e:
            self.set_error(title=_("Simulation failed."), message=str(e))
        finally:
            dialog.destroy()

    def set_output_file_content(self, output_file):
        self.raw_data_window.clear_buffer()

        with open(output_file, 'r') as f:
            lines = f.readlines()
            for line in lines:
                self.raw_data_window.insert_text(line)

        self.raw_data_window.set_subtitle(output_file)

    def on_execution_log_clicked(self, button, response_id):
        if self.execution_log_window is None:
            self.execution_log_window = console_gui.ConsoleOutputWindow(_("Execution log"))
        self.execution_log_window.show_all()

    def set_execution_log(self, file_name, content):
        self.execution_log_window.clear_buffer()
        self.execution_log_window.insert_text(content)

        self.execution_log_window.set_subtitle(file_name)


    def start_file_monitor(self):
        if self.schematic_file_path is not None:
            path = self.schematic_file_path
        elif self.netlist_file_path is not None:
            path = self.netlist_file_path
        else:
            return
        target_file = Gio.File.new_for_path(path)
        self.file_monitor = target_file.monitor_file(Gio.FileMonitorFlags.NONE, None)
        self.file_monitor.connect("changed", self.on_file_changed)

    def stop_file_monitor(self):
        if self.file_monitor is not None:
            self.file_monitor.cancel()

    def on_file_changed(self, file_monitor, _file, other_file, event_type):
        ''' on_file_changed(file_monitor,_file, other_file, event_type) -> None

        Callback function for file monitor on netlist file
        '''
        if event_type == Gio.FileMonitorEvent.CHANGED or event_type == Gio.FileMonitorEvent.CREATED:
            self.set_error(title=_("Opened file changed on disk."), message=None, message_type=Gtk.MessageType.WARNING, actions=[(_("Reload"), 1000, self.on_infobar_reload_clicked)])

    def on_infobar_reload_clicked(self, button, response_id):
        if self.schematic_file_path is not None:
            self.load_file(self.schematic_file_path)
        elif self.netlist_file_path is not None:
            self.load_file(self.netlist_file_path)
        else:
            raise Exception("self.schematic_file_path and self.netlist_file_path are None")

    def on_source_buffer_modified_changed(self, data):
        if self.source_buffer.get_modified():
            self.hb.set_title("* " + self.circuit_title)
        else:
            self.hb.set_title(self.circuit_title)

    def load_file(self, path):
        '''
        load a file, converts it to netlist if needed and updates program state
        '''
        self.netlist_file_path = None
        self.schematic_file_path = None
        file_content = None
            #schematic to netlist conversion

        if os.path.splitext(path)[1] == ".sch":
            # Try convert schematic to netlist
            try:
                ngspice_simulation.Gnetlist.create_netlist_file(path, path + ".net")
                self.netlist_file_path = path + ".net"
                self.schematic_file_path = path
            except Exception as e:
                self.set_error(title=_("Schematic could not be converted to netlist."), message=str(e))
                self.netlist_file_path = None
                self.schematic_file_path = None
                return
        else:
            self.netlist_file_path = path

        # Read netlist file
        if self.netlist_file_path is not None:
            with open(self.netlist_file_path) as f:
                file_content = f.read()

        # Set a file monitor
        self.start_file_monitor()

        if file_content is not None and self.netlist_file_path is not None:
            #Set window title
            netlist = ngspice_simulation.Netlist(file_content)
            self.circuit_title = netlist.get_title()
            if self.circuit_title is not None:
                self.hb.set_title(self.circuit_title)
            else:
                self.hb.set_title("")
            self.hb.set_subtitle(self.netlist_file_path)

            # Dismiss older errors
            self.dismiss_error()

            # Set content on source view
            self._open_state("opened")
            self.source_buffer.props.text = file_content
            self.source_buffer.set_modified(False)
            self.simulate_button.props.sensitive = True
            self.canvas.show()

    def on_button_open_clicked(self, button):
        #Filechooserdialog initialization
        dialog = Gtk.FileChooserDialog(_("Please choose a file"), self, Gtk.FileChooserAction.OPEN,
                                       (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_OPEN, Gtk.ResponseType.OK))

        netlist_filter = Gtk.FileFilter()
        netlist_filter.set_name(_("Netlist"))
        netlist_filter.add_pattern("*.net")
        netlist_filter.add_pattern("*.cir")
        netlist_filter.add_pattern("*.ckt")
        dialog.add_filter(netlist_filter)

        gschem_filter = Gtk.FileFilter()
        gschem_filter.set_name(_("GEDA schematic"))
        gschem_filter.add_mime_type("application/x-geda-schematic")
        dialog.add_filter(gschem_filter)

        all_filter = Gtk.FileFilter()
        all_filter.set_name(_("Supported files"))
        all_filter.add_pattern("*.net")
        all_filter.add_pattern("*.cir")
        all_filter.add_pattern("*.ckt")
        all_filter.add_mime_type("application/x-geda-schematic")
        dialog.add_filter(all_filter)

        dialog.set_filter(all_filter)

        response = dialog.run()

        if response == Gtk.ResponseType.OK:
            try:
                path = dialog.get_filename()
                dialog.destroy()
                self.load_file(path)
            except Exception as e:
                self.set_error(title=_("File could not be loaded."), message=str(e.message))
        else:
            dialog.destroy()

    def save_netlist_file(self):
        """Save file on self.netlist_file_path path."""
        self.stop_file_monitor()
        with open(self.netlist_file_path, "w") as f:
            f.write(self.source_buffer.props.text)
        self.start_file_monitor()
        self.source_buffer.set_modified(False)


class InfoMessageBar(Gtk.InfoBar):

    def __init__(self):
        Gtk.InfoBar.__init__(self)
        self.set_show_close_button(True)

        self.title_label = Gtk.Label(label="", use_markup=True, halign=Gtk.Align.START, justify=Gtk.Justification.LEFT, )
        self.subtitle_label = Gtk.Label(label="", use_markup=True, halign=Gtk.Align.START, justify=Gtk.Justification.LEFT, wrap=True)

        self.infobar_content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.infobar_content_box.pack_start(self.title_label, False, False, 0)
        self.infobar_content_box.pack_start(self.subtitle_label, True, True, 0)
        self.get_content_area().add(self.infobar_content_box)

        self.user_responses = {} # {response_id: callback_function, ...}

        self.connect("response", self._on_infobar_close_clicked)

    @property
    def message_title(self):
        return self.title_label.props.label

    @message_title.setter
    def message_title(self, value):
        self.title_label.props.label = "<b>" + value + "</b>"

    @property
    def message_subtitle(self):
        return self.subtitle_label.props.label

    @message_subtitle.setter
    def message_subtitle(self, value):
        self.subtitle_label.props.label = "<small>" + value + "</small>"

    def _on_infobar_close_clicked(self, button, response_id):
        if response_id == int(Gtk.ResponseType.CLOSE):
            self.props.visible = False
        else:
            self.user_responses[response_id](button, response_id)
            self.props.visible = False
