#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Subliminal Nemo Enhanced Extension
#
# Una interfaz mejorada para descargar subtítulos desde Nemo

import os
import subprocess
import gettext
import gi
import json
from pathlib import Path

gi.require_version('Gtk', '3.0')
gi.require_version('Nemo', '3.0')
from gi.repository import GObject, Gtk, Nemo, Gio, GLib, Pango

_ = gettext.gettext

# Configuración por defecto
DEFAULT_CONFIG = {
    'languages': ['spa', 'eng'],
    # Solo incluir proveedores compatibles con la versión actual de Subliminal
    'providers': ['opensubtitles', 'addic7ed', 'tvsubtitles'],
    'single': True,
    'force': True,
    'hearing_impaired': False,
    'min_score': 0,
    'open_subtitles_username': '',
    'open_subtitles_password': '',
    'addic7ed_username': '',
    'addic7ed_password': ''
}

CONFIG_FILE = os.path.expanduser('~/.config/subliminal-nemo/config.json')
LOG_FILE = os.path.expanduser('~/.cache/subliminal-nemo/log.txt')

class SubliminalConfigDialog(Gtk.Dialog):
    def __init__(self, parent, config):
        super().__init__(
            title=_("Configuración de Subliminal"),
            flags=0,
            modal=True
        )
        
        # Configuración de la ventana
        if parent is not None:
            self.set_transient_for(parent)
        self.set_position(Gtk.WindowPosition.CENTER_ON_PARENT)
        
        self.config = config
        self.set_default_size(600, 700)
        self.set_border_width(10)
        
        # Aplicar estilos CSS para mejorar la apariencia
        self._apply_styles()
        
        # Contenedor principal
        box = self.get_content_area()
        
        # Notebook con pestañas
        notebook = Gtk.Notebook()
        notebook.set_show_tabs(True)
        notebook.set_scrollable(True)
        box.pack_start(notebook, True, True, 0)
        
        # Pestaña de configuración general
        general_box = self._create_general_tab()
        notebook.append_page(general_box, Gtk.Label(label=_("General")))
        
        # Pestaña de idiomas
        languages_box = self._create_languages_tab()
        notebook.append_page(languages_box, Gtk.Label(label=_("Idiomas")))
        
        # Pestaña de cuentas
        accounts_box = self._create_accounts_tab()
        notebook.append_page(accounts_box, Gtk.Label(label=_("Cuentas")))
        
        # Botones de acción
        self.add_button(_("Cancelar"), Gtk.ResponseType.CANCEL)
        self.add_button(_("Aplicar"), Gtk.ResponseType.APPLY)
        self.add_button(_("Aceptar"), Gtk.ResponseType.OK)
        
        self.show_all()
    
    def _apply_styles(self):
        """Aplica estilos CSS al diálogo"""
        style_provider = Gtk.CssProvider()
        css = """
            .frame-title {
                font-weight: bold;
                font-size: 1.1em;
                margin: 10px 0 5px 0;
            }
            .section-title {
                font-weight: bold;
                margin: 15px 0 5px 0;
            }
            .setting-row {
                margin: 8px 0;
                padding: 5px;
                border-radius: 4px;
            }
            .setting-row:hover {
                background-color: rgba(0,0,0,0.05);
            }
            .switch {
                margin-left: 10px;
            }
        """
        style_provider.load_from_data(css.encode())
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            style_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
    
    def _create_general_tab(self):
        """Crea la pestaña de configuración general"""
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(12)
        box.set_margin_bottom(12)
        box.set_margin_start(12)
        box.set_margin_end(12)
        
        # Sección de comportamiento
        behavior_label = Gtk.Label()
        behavior_label.set_markup("<span class='frame-title'>{}</span>".format(_("Comportamiento")))
        behavior_label.set_halign(Gtk.Align.START)
        box.pack_start(behavior_label, False, False, 0)
        
        # Forzar descarga
        self.force_switch = Gtk.Switch()
        self.force_switch.set_active(self.config.get('force', True))
        self._add_setting_row(
            box,
            _("Forzar descarga"),
            _("Descargar subtítulos incluso si ya existen"),
            self.force_switch
        )
        
        # Un solo subtítulo
        self.single_switch = Gtk.Switch()
        self.single_switch.set_active(self.config.get('single', True))
        self._add_setting_row(
            box,
            _("Un solo subtítulo"),
            _("Descargar solo el mejor subtítulo para cada idioma"),
            self.single_switch
        )
        
        # Subtítulos para sordos
        self.hearing_impaired_switch = Gtk.Switch()
        self.hearing_impaired_switch.set_active(self.config.get('hearing_impaired', False))
        self._add_setting_row(
            box,
            _("Subtítulos para sordos"),
            _("Incluir efectos de sonido y música en los subtítulos"),
            self.hearing_impaired_switch
        )
        
        # Puntuación mínima
        score_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.min_score = Gtk.SpinButton.new_with_range(0, 100, 1)
        self.min_score.set_value(self.config.get('min_score', 0))
        self.min_score.set_halign(Gtk.Align.START)
        
        score_label = Gtk.Label(label=_("Puntuación mínima"))
        score_label.set_tooltip_text(_("Puntuación mínima aceptable para los subtítulos (0-100)"))
        
        score_box.pack_start(score_label, False, False, 0)
        score_box.pack_end(self.min_score, False, False, 0)
        
        score_row = Gtk.ListBoxRow()
        score_row.add(score_box)
        box.pack_start(score_row, False, False, 0)
        
        return box
    
    def _create_languages_tab(self):
        """Crea la pestaña de configuración de idiomas"""
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(12)
        box.set_margin_bottom(12)
        box.set_margin_start(12)
        box.set_margin_end(12)
        
        # Título y descripción
        title = Gtk.Label()
        title.set_markup("<span class='frame-title'>{}</span>".format(_("Idiomas preferidos")))
        title.set_halign(Gtk.Align.START)
        box.pack_start(title, False, False, 0)
        
        desc = Gtk.Label(label=_("Selecciona los idiomas en orden de preferencia:"))
        desc.set_halign(Gtk.Align.START)
        desc.set_line_wrap(True)
        box.pack_start(desc, False, False, 5)
        
        # Modelo de datos para la lista de idiomas
        self.language_store = Gtk.ListStore(str, str, bool)  # code, name, active
        
        # Lista de idiomas disponibles
        self.available_languages = [
            ('spa', _('Español')),
            ('eng', _('Inglés')),
            ('fra', _('Francés')),
            ('ita', _('Italiano')),
            ('por', _('Portugués')),
            ('deu', _('Alemán')),
            ('jpn', _('Japonés')),
            ('kor', _('Coreano')),
            ('zho', _('Chino')),
            ('rus', _('Ruso')),
            ('ara', _('Árabe')),
            ('nld', _('Holandés')),
            ('swe', _('Sueco')),
            ('tur', _('Turco')),
            ('pol', _('Polaco')),
            ('dan', _('Danés')),
            ('fin', _('Finlandés')),
            ('nor', _('Noruego')),
            ('ell', _('Griego')),
            ('hun', _('Húngaro'))
        ]
        
        # Marcar los idiomas seleccionados
        selected_languages = set(self.config.get('languages', ['spa', 'eng']))
        for code, name in self.available_languages:
            self.language_store.append([code, name, code in selected_languages])
        
        # Crear TreeView con selección múltiple
        treeview = Gtk.TreeView(model=self.language_store)
        treeview.set_headers_visible(False)
        treeview.set_activate_on_single_click(True)
        treeview.connect("row-activated", self._on_language_activated)
        
        # Columna de selección
        renderer_toggle = Gtk.CellRendererToggle()
        renderer_toggle.set_activatable(True)
        renderer_toggle.connect("toggled", self._on_language_toggled)
        column_toggle = Gtk.TreeViewColumn("", renderer_toggle, active=2)
        treeview.append_column(column_toggle)
        
        # Columna de nombre de idioma
        renderer_text = Gtk.CellRendererText()
        column_text = Gtk.TreeViewColumn(_("Idioma"), renderer_text, text=1)
        treeview.append_column(column_text)
        
        # Añadir scroll
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.add(treeview)
        scrolled.set_size_request(-1, 300)
        scrolled.set_shadow_type(Gtk.ShadowType.IN)
        
        # Botones de acción para idiomas
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        button_box.set_halign(Gtk.Align.END)
        
        select_all_btn = Gtk.Button(label=_("Seleccionar todo"))
        select_all_btn.connect("clicked", self._on_select_all_languages, True)
        
        select_none_btn = Gtk.Button(label=_("Deseleccionar todo"))
        select_none_btn.connect("clicked", self._on_select_all_languages, False)
        
        button_box.pack_start(select_all_btn, False, False, 0)
        button_box.pack_start(select_none_btn, False, False, 0)
        
        box.pack_start(scrolled, True, True, 0)
        box.pack_start(button_box, False, False, 5)
        
        return box
    
    def _create_accounts_tab(self):
        """Crea la pestaña de configuración de cuentas"""
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15)
        box.set_margin_top(12)
        box.set_margin_bottom(12)
        box.set_margin_start(12)
        box.set_margin_end(12)
        
        # Sección de OpenSubtitles
        os_frame = Gtk.Frame()
        os_frame.set_shadow_type(Gtk.ShadowType.ETCHED_IN)
        os_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        os_box.set_margin_top(8)
        os_box.set_margin_bottom(8)
        os_box.set_margin_start(8)
        os_box.set_margin_end(8)
        
        os_label = Gtk.Label()
        os_label.set_markup("<b>{}</b>".format(_("OpenSubtitles")))
        os_label.set_halign(Gtk.Align.START)
        os_box.pack_start(os_label, False, False, 0)
        
        # Campos de usuario y contraseña
        self.os_username = Gtk.Entry()
        self.os_username.set_placeholder_text(_("Usuario de OpenSubtitles"))
        self.os_username.set_text(self.config.get('open_subtitles_username', ''))
        os_box.pack_start(self._create_entry_row(_("Usuario:"), self.os_username), False, False, 5)
        
        self.os_password = Gtk.Entry()
        self.os_password.set_placeholder_text(_("Contraseña"))
        self.os_password.set_text(self.config.get('open_subtitles_password', ''))
        self.os_password.set_visibility(False)
        self.os_password.set_input_purpose(Gtk.InputPurpose.PASSWORD)
        
        # Botón para mostrar/ocultar contraseña
        pass_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        pass_box.pack_start(self.os_password, True, True, 0)
        
        toggle_pass = Gtk.ToggleButton()
        toggle_pass.set_image(Gtk.Image.new_from_icon_name("changes-allow-symbolic", Gtk.IconSize.BUTTON))
        toggle_pass.connect("toggled", self._on_toggle_password_visibility, self.os_password)
        pass_box.pack_start(toggle_pass, False, False, 0)
        
        os_box.pack_start(self._create_entry_row(_("Contraseña:"), pass_box), False, False, 5)
        
        # Enlace para crear cuenta
        link = Gtk.LinkButton(
            uri="https://www.opensubtitles.org/es/users/signup",
            label=_("Crear una cuenta"),
            halign=Gtk.Align.END
        )
        os_box.pack_start(link, False, False, 5)
        
        os_frame.add(os_box)
        
        # Sección de Addic7ed
        addic7ed_frame = Gtk.Frame()
        addic7ed_frame.set_shadow_type(Gtk.ShadowType.ETCHED_IN)
        addic7ed_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        addic7ed_box.set_margin_top(8)
        addic7ed_box.set_margin_bottom(8)
        addic7ed_box.set_margin_start(8)
        addic7ed_box.set_margin_end(8)
        
        addic7ed_label = Gtk.Label()
        addic7ed_label.set_markup("<b>{}</b>".format(_("Addic7ed")))
        addic7ed_label.set_halign(Gtk.Align.START)
        addic7ed_box.pack_start(addic7ed_label, False, False, 0)
        
        # Campos de usuario y contraseña
        self.addic7ed_username = Gtk.Entry()
        self.addic7ed_username.set_placeholder_text(_("Usuario de Addic7ed"))
        self.addic7ed_username.set_text(self.config.get('addic7ed_username', ''))
        addic7ed_box.pack_start(
            self._create_entry_row(_("Usuario:"), self.addic7ed_username),
            False, False, 5
        )
        
        self.addic7ed_password = Gtk.Entry()
        self.addic7ed_password.set_placeholder_text(_("Contraseña"))
        self.addic7ed_password.set_text(self.config.get('addic7ed_password', ''))
        self.addic7ed_password.set_visibility(False)
        self.addic7ed_password.set_input_purpose(Gtk.InputPurpose.PASSWORD)
        
        # Botón para mostrar/ocultar contraseña
        addic7ed_pass_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        addic7ed_pass_box.pack_start(self.addic7ed_password, True, True, 0)
        
        addic7ed_toggle = Gtk.ToggleButton()
        addic7ed_toggle.set_image(Gtk.Image.new_from_icon_name("changes-allow-symbolic", Gtk.IconSize.BUTTON))
        addic7ed_toggle.connect("toggled", self._on_toggle_password_visibility, self.addic7ed_password)
        addic7ed_pass_box.pack_start(addic7ed_toggle, False, False, 0)
        
        addic7ed_box.pack_start(
            self._create_entry_row(_("Contraseña:"), addic7ed_pass_box),
            False, False, 5
        )
        
        # Enlace para crear cuenta
        addic7ed_link = Gtk.LinkButton(
            uri="https://www.addic7ed.com/register.php",
            label=_("Crear una cuenta"),
            halign=Gtk.Align.END
        )
        addic7ed_box.pack_start(addic7ed_link, False, False, 5)
        
        addic7ed_frame.add(addic7ed_box)
        
        # Agregar secciones al contenedor principal
        box.pack_start(os_frame, False, False, 0)
        box.pack_start(addic7ed_frame, False, False, 0)
        
        # Nota informativa
        note = Gtk.Label()
        note.set_markup(
            "<small><i>{}</i></small>".format(
                _("Las credenciales se guardan de forma segura en tu sistema.")
            )
        )
        note.set_halign(Gtk.Align.START)
        box.pack_start(note, False, False, 10)
        
        return box
    
    def _add_setting_row(self, container, label, tooltip, widget):
        """Añade una fila de configuración con etiqueta y widget"""
        row = Gtk.ListBoxRow()
        row_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        row_box.set_margin_top(6)
        row_box.set_margin_bottom(6)
        
        label_widget = Gtk.Label(label=label)
        label_widget.set_halign(Gtk.Align.START)
        label_widget.set_tooltip_text(tooltip)
        
        row_box.pack_start(label_widget, True, True, 0)
        row_box.pack_end(widget, False, False, 0)
        
        row.add(row_box)
        container.pack_start(row, False, False, 0)
        
        return row
    
    def _create_entry_row(self, label_text, widget):
        """Crea una fila con etiqueta y widget de entrada"""
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        
        label = Gtk.Label(label=label_text)
        label.set_halign(Gtk.Align.START)
        label.set_size_request(100, -1)
        
        box.pack_start(label, False, False, 0)
        box.pack_start(widget, True, True, 0)
        
        return box
    
    def _on_toggle_password_visibility(self, button, entry):
        """Alterna la visibilidad de la contraseña"""
        visible = button.get_active()
        entry.set_visibility(visible)
        
        # Cambiar el icono según el estado
        if visible:
            button.set_image(Gtk.Image.new_from_icon_name("changes-prevent-symbolic", Gtk.IconSize.BUTTON))
        else:
            button.set_image(Gtk.Image.new_from_icon_name("changes-allow-symbolic", Gtk.IconSize.BUTTON))
    
    def _on_language_toggled(self, renderer, path):
        """Maneja el evento de cambio en la selección de idiomas"""
        self.language_store[path][2] = not self.language_store[path][2]
    
    def _on_language_activated(self, treeview, path, column):
        """Maneja la activación de una fila de idioma"""
        self.language_store[path][2] = not self.language_store[path][2]
    
    def _on_select_all_languages(self, button, select):
        """Selecciona o deselecciona todos los idiomas"""
        for row in self.language_store:
            row[2] = select
    
    def get_config(self):
        """Obtiene la configuración actual del diálogo"""
        config = self.config.copy()
        
        # Obtener idiomas seleccionados
        selected_languages = []
        for row in self.language_store:
            if row[2]:  # Si está activo
                selected_languages.append(row[0])
        
        # Si no hay idiomas seleccionados, usar los predeterminados
        if not selected_languages:
            selected_languages = ['spa', 'eng']
        
        config['languages'] = selected_languages
        config['force'] = self.force_switch.get_active()
        config['single'] = self.single_switch.get_active()
        config['hearing_impaired'] = self.hearing_impaired_switch.get_active()
        config['min_score'] = int(self.min_score.get_value())
        
        # Credenciales
        config['open_subtitles_username'] = self.os_username.get_text().strip()
        config['open_subtitles_password'] = self.os_password.get_text().strip()
        config['addic7ed_username'] = self.addic7ed_username.get_text().strip()
        config['addic7ed_password'] = self.addic7ed_password.get_text().strip()
        
        return config
        """Crea una fila con una etiqueta y un widget"""
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        row.set_margin_bottom(6)
        
        label = Gtk.Label(label=label_text, xalign=0)
        label.set_hexpand(True)
        
        row.pack_start(label, True, True, 0)
        row.pack_start(widget, False, False, 0)
        
        if tooltip_text:
            row.set_tooltip_text(tooltip_text)
            widget.set_tooltip_text(tooltip_text)
        
        box.pack_start(row, False, True, 0)
    
    def get_config(self):
        """Obtiene la configuración actual del diálogo"""
        config = self.config.copy()
        
        # Configuración general
        config['force'] = self.force_switch.get_active()
        config['single'] = self.single_switch.get_active()
        config['hearing_impaired'] = self.hearing_impaired_switch.get_active()
        config['min_score'] = self.min_score.get_value_as_int()
        
        # Idiomas seleccionados
        config['languages'] = [
            row[0] for row in self.language_store if row[2]  # row[2] es el estado del toggle
        ]
        
        # Si no hay idiomas seleccionados, usar los predeterminados
        if not config['languages']:
            config['languages'] = ['spa', 'eng']
        
        # Cuentas
        config['open_subtitles_username'] = self.os_username.get_text()
        config['open_subtitles_password'] = self.os_password.get_text()
        config['addic7ed_username'] = self.addic7ed_username.get_text()
        config['addic7ed_password'] = self.addic7ed_password.get_text()
        
        return config


class SubliminalExtension(GObject.GObject, Nemo.MenuProvider):
    def __init__(self):
        self.config = self.load_config()
        self.setup_directories()
    
    def setup_directories(self):
        """Crea los directorios necesarios si no existen"""
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    
    def load_config(self):
        """Carga la configuración desde el archivo o usa valores por defecto"""
        if not os.path.exists(CONFIG_FILE):
            return DEFAULT_CONFIG.copy()
            
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                
                # Asegurarse de que todos los valores por defecto estén presentes
                for key, value in DEFAULT_CONFIG.items():
                    if key not in config:
                        config[key] = value
                
                # Filtrar proveedores no compatibles
                if 'providers' in config:
                    compatible_providers = {
                        'addic7ed', 'bsplayer', 'gestdown', 'napiprojekt', 
                        'opensubtitles', 'opensubtitlescom', 'opensubtitlescomvip', 
                        'opensubtitlesvip', 'podnapisi', 'subtitulamos', 'tvsubtitles'
                    }
                    
                    # Filtrar solo proveedores compatibles
                    filtered_providers = [p for p in config['providers'] if p in compatible_providers]
                    
                    # Si no quedan proveedores compatibles, usar los predeterminados
                    if not filtered_providers:
                        config['providers'] = DEFAULT_CONFIG['providers']
                    else:
                        config['providers'] = filtered_providers
                
                return config
                
        except Exception as e:
            self.log_error(f"Error al cargar la configuración: {str(e)}")
            return DEFAULT_CONFIG.copy()
    
    def save_config(self, config):
        """Guarda la configuración en el archivo"""
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(config, f, indent=4)
            return True
        except Exception as e:
            self.log_error(f"Error al guardar la configuración: {str(e)}")
            return False
    
    def log_error(self, message):
        """Registra un mensaje de error en el archivo de registro"""
        try:
            with open(LOG_FILE, 'a') as f:
                f.write(f"{message}\n")
        except:
            pass
    
    def show_error_dialog(self, parent, message):
        """Muestra un diálogo de error"""
        dialog = Gtk.MessageDialog(
            transient_for=parent,
            flags=0,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.CLOSE,
            text=_("Error")
        )
        dialog.format_secondary_text(message)
        dialog.run()
        dialog.destroy()
    
    def show_progress_dialog(self, parent, files):
        """Muestra un diálogo con el progreso de la descarga"""
        dialog = Gtk.Dialog(
            title=_("Descargando subtítulos"),
            flags=0
        )
        
        # Si tenemos una ventana padre, la configuramos como transitoria
        if parent is not None:
            dialog.set_transient_for(parent)
        dialog.set_default_size(400, 300)
        
        # Configurar la ventana
        content_area = dialog.get_content_area()
        content_area.set_spacing(6)
        
        # Barra de progreso
        progress_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        progress_bar = Gtk.ProgressBar()
        progress_box.pack_start(progress_bar, False, False, 6)
        
        # Área de texto para el registro
        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_hexpand(True)
        scrolled_window.set_vexpand(True)
        
        text_view = Gtk.TextView()
        text_view.set_editable(False)
        text_view.set_wrap_mode(Gtk.WrapMode.WORD)
        text_view.set_monospace(True)
        
        # Configurar fuente monoespaciada
        font_desc = Pango.FontDescription("Monospace 9")
        text_view.override_font(font_desc)
        
        scrolled_window.add(text_view)
        
        # Botón de cerrar
        close_button = dialog.add_button(_("Cerrar"), Gtk.ResponseType.CLOSE)
        close_button.set_sensitive(False)
        
        content_area.pack_start(progress_box, False, False, 6)
        content_area.pack_start(scrolled_window, True, True, 6)
        
        dialog.show_all()
        
        # Iniciar la descarga en segundo plano
        self.start_download(dialog, files, progress_bar, text_view, close_button)
        
        # Manejar la respuesta del diálogo
        response = dialog.run()
        if response == Gtk.ResponseType.CLOSE:
            dialog.destroy()
    
    def start_download(self, dialog, files, progress_bar, text_view, close_button):
        """Inicia el proceso de descarga en segundo plano"""
        def append_log(text):
            buffer = text_view.get_buffer()
            end_iter = buffer.get_end_iter()
            buffer.insert(end_iter, f"{text}\n")
            
            # Desplazarse al final
            mark = buffer.create_mark(None, end_iter, False)
            text_view.scroll_to_mark(mark, 0.0, True, 0.0, 1.0)
        
        def update_progress(progress, message):
            progress_bar.set_fraction(progress)
            append_log(message)
            
            # Actualizar la interfaz
            while Gtk.events_pending():
                Gtk.main_iteration_do(False)
        
        def download_thread():
            total_files = len(files)
            for i, file_info in enumerate(files):
                if file_info.get_uri_scheme() != 'file':
                    continue
                
                filename = file_info.get_location().get_path()
                if not os.path.isfile(filename):
                    continue
                
                # Actualizar progreso
                progress = i / total_files
                update_progress(progress, f"Procesando: {os.path.basename(filename)}")
                
                # Construir el comando base
                cmd = ['subliminal', 'download']
                
                # Añadir banderas opcionales
                if self.config['force']:
                    cmd.append('--force')
                if self.config['single']:
                    cmd.append('--single')
                if self.config['hearing_impaired']:
                    cmd.append('--hearing-impaired')
                
                # Añadir puntuación mínima
                cmd.extend(['--min-score', str(self.config['min_score'])])
                
                # Añadir proveedores (uno por uno)
                for provider in self.config['providers']:
                    cmd.extend(['--provider', provider])
                
                # Configurar credenciales como variables de entorno
                env = os.environ.copy()
                
                # Configurar credenciales de OpenSubtitles
                if self.config['open_subtitles_username'] and self.config['open_subtitles_password']:
                    env['SUBLIMINAL_OPENSUBTITLES_USERNAME'] = self.config['open_subtitles_username']
                    env['SUBLIMINAL_OPENSUBTITLES_PASSWORD'] = self.config['open_subtitles_password']
                
                # Configurar credenciales de Addic7ed (si es necesario)
                if self.config['addic7ed_username'] and self.config['addic7ed_password']:
                    env['SUBLIMINAL_ADDIC7ED_USERNAME'] = self.config['addic7ed_username']
                    env['SUBLIMINAL_ADDIC7ED_PASSWORD'] = self.config['addic7ed_password']
                
                # Añadir idiomas (cada uno como un argumento separado)
                cmd.append('-l')
                cmd.extend(self.config['languages'])
                
                # Añadir el archivo
                cmd.append(filename)
                
                # Filtrar cadenas vacías
                cmd = [arg for arg in cmd if arg]
                
                try:
                    # Ejecutar el comando con las variables de entorno
                    process = subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        universal_newlines=True,
                        env=env
                    )
                    
                    # Leer la salida en tiempo real
                    for line in process.stdout:
                        append_log(line.strip())
                    
                    # Leer errores
                    for line in process.stderr:
                        append_log(f"ERROR: {line.strip()}")
                    
                    process.wait()
                    
                    if process.returncode == 0:
                        append_log(f"✓ Subtítulos descargados para {os.path.basename(filename)}")
                    else:
                        append_log(f"✗ Error al descargar subtítulos para {os.path.basename(filename)}")
                    
                except Exception as e:
                    append_log(f"✗ Error al procesar {os.path.basename(filename)}: {str(e)}")
            
            # Actualizar la interfaz al finalizar
            GLib.idle_add(update_progress, 1.0, "\n¡Descarga completada!")
            GLib.idle_add(close_button.set_sensitive, True)
        
        # Iniciar el hilo de descarga
        import threading
        thread = threading.Thread(target=download_thread)
        thread.daemon = True
        thread.start()
    
    def show_config_dialog(self, parent):
        """Muestra el diálogo de configuración"""
        dialog = SubliminalConfigDialog(parent, self.config)
        
        # Si no hay ventana padre, centrar el diálogo en la pantalla
        if parent is None:
            dialog.set_position(Gtk.WindowPosition.CENTER_ON_PARENT)
            
        response = dialog.run()
        
        if response == Gtk.ResponseType.OK:
            new_config = dialog.get_config()
            if new_config != self.config:
                self.config = new_config
                self.save_config(self.config)
    
    def menu_activate_cb(self, menu, files):
        """Maneja la activación del menú"""
        # En Nemo, no podemos obtener fácilmente la ventana principal desde el menú
        # Pasamos None como ventana principal
        self.show_progress_dialog(None, files)
    
    def config_activate_cb(self, menu):
        """Maneja la activación de la opción de configuración"""
        # En Nemo, no podemos obtener fácilmente la ventana principal desde el menú
        # Pasamos None como ventana principal
        self.show_config_dialog(None)
    
    def get_file_items(self, window, files):
        """Devuelve los elementos del menú contextual para archivos"""
        # Solo mostrar para archivos de video
        video_extensions = ('.mkv', '.mp4', '.avi', '.mov', '.wmv', '.flv', '.m4v', '.mpg', '.mpeg')
        
        for file_info in files:
            if file_info.is_gone() or file_info.is_directory():
                return []
            
            file_path = file_info.get_location().get_path()
            if not file_path or not file_path.lower().endswith(video_extensions):
                return []
        
        # Crear el elemento de menú principal
        menu_item = Nemo.MenuItem(
            name='Subliminal::download_subtitles',
            label=_('Descargar subtítulos'),
            tip=_('Descargar subtítulos con Subliminal')
        )
        menu_item.connect('activate', self.menu_activate_cb, files)
        
        return [menu_item]
    
    def get_background_items(self, window, file):
        """Devuelve los elementos del menú contextual para el fondo"""
        # Crear el elemento de menú de configuración
        menu_item = Nemo.MenuItem(
            name='Subliminal::configure',
            label=_('Configurar Subliminal'),
            tip=_('Configurar las opciones de Subliminal')
        )
        menu_item.connect('activate', self.config_activate_cb)
        
        return [menu_item]
