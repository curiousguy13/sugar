# Copyright (C) 2008, OLPC
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301 USA

import gtk
import gobject
import pango
from gettext import gettext as _

from sugar.graphics import style
from sugar.graphics.icon import Icon

from jarabe.controlpanel.sectionview import SectionView
from jarabe.controlpanel.inlinealert import InlineAlert

CLASS = 'Language'
ICON = 'module-keyboard'
TITLE = _('Keyboard')

_APPLY_TIMEOUT = 3000

class LayoutCombo(gtk.HBox):
    __gsignals__ = {
        'selection-changed' : (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE,
                            (gobject.TYPE_STRING, gobject.TYPE_INT))
        }
    def __init__(self, xkb, n):
        gtk.HBox.__init__(self)
        self._xkb = xkb
        self._index = n

        self.set_border_width(style.DEFAULT_SPACING)
        self.set_spacing(style.DEFAULT_SPACING)

        label = gtk.Label(' <b>%s</b> ' % str(n+1))
        label.set_use_markup(True)
        label.modify_fg(gtk.STATE_NORMAL,
                    style.COLOR_SELECTION_GREY.get_gdk_color())
        label.set_alignment(0.5, 0.5)
        self.pack_start(label, expand=False)

        self._klang_store = gtk.ListStore(gobject.TYPE_STRING, gobject.TYPE_STRING)
        for description, name in self._xkb.get_languages():
            self._klang_store.append([name, description])

        self._klang_combo = gtk.ComboBox(model = self._klang_store)
        self._klang_combo_changed_id = \
            self._klang_combo.connect('changed', self._klang_combo_changed_cb)
        cell = gtk.CellRendererText()
        cell.props.ellipsize = pango.ELLIPSIZE_MIDDLE
        self._klang_combo.pack_start(cell)
        self._klang_combo.add_attribute(cell, 'text', 1)
        self.pack_start(self._klang_combo, expand=True, fill = True)

        self._kvariant_store = None
        self._kvariant_combo = gtk.ComboBox(model = None)
        self._kvariant_combo_changed_id = \
            self._kvariant_combo.connect('changed', self._kvariant_combo_changed_cb)
        cell = gtk.CellRendererText()
        cell.props.ellipsize = pango.ELLIPSIZE_MIDDLE
        self._kvariant_combo.pack_start(cell)
        self._kvariant_combo.add_attribute(cell, 'text', 1)
        self.pack_start(self._kvariant_combo, expand=True, fill = True)

        self._klang_combo.set_active(self._index)

    def select_layout(self, layout):
        self._kvariant_combo.handler_block(self._kvariant_combo_changed_id)
        for i in range(0, len(self._klang_store)):
            self._klang_combo.set_active(i)
            for j in range(0, len(self._kvariant_store)):
                if self._kvariant_store[j][0] == layout:
                    self._kvariant_combo.set_active(j)
                    self._kvariant_combo.handler_unblock(self._kvariant_combo_changed_id)
                    return True

        self._kvariant_combo.handler_unblock(self._kvariant_combo_changed_id)
        self._klang_combo.set_active(0)
        return False

    def get_layout(self):
        iter = self._kvariant_combo.get_active_iter()
        model = self._kvariant_combo.get_model()
        return model.get(iter, 0)[0]

    def _set_kvariant_store(self, lang):
        self._kvariant_store = gtk.ListStore(gobject.TYPE_STRING, gobject.TYPE_STRING)
        for description, name in self._xkb.get_layouts_for_language(lang):
            self._kvariant_store.append([name, description])
        self._kvariant_combo.set_model(self._kvariant_store)
        self._kvariant_combo.set_active(0)

    def _klang_combo_changed_cb(self, combobox):
        it = combobox.get_active_iter()
        model = combobox.get_model()
        lang = model.get(it, 0)[0]
        self._set_kvariant_store(lang)
    
    def _kvariant_combo_changed_cb(self, combobox):
        it = combobox.get_active_iter()
        model = combobox.get_model()
        layout = model.get(it, 0)[0]
        self.emit('selection-changed', layout, self._index)


class Keyboard(SectionView):
    def __init__(self, model, alerts):
        SectionView.__init__(self)

        self._model = model

        self._kmodel = None
        self._selected_kmodel = None
        
        self._klayouts = []
        self._selected_klayouts = []
        
        self._group_switch_option = None
        self._selected_group_switch_option = None

        self.set_border_width(style.DEFAULT_SPACING * 2)
        self.set_spacing(style.DEFAULT_SPACING)
        
        self._layout_table = gtk.Table(rows = 4, columns = 2, homogeneous = False)

        self._xkb = model.XKB(self.get_display())
        self._layout_combo_list = []
        self._layout_addremovebox_list = []

        scrollwindow = gtk.ScrolledWindow()
        scrollwindow.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        self.pack_start(scrollwindow, expand=True)
        scrollwindow.show()

        self._vbox = gtk.VBox()
        scrollwindow.add_with_viewport(self._vbox)
        
        self.__kmodel_sid = None
        self.__layout_sid = None
        self.__group_switch_sid = None

        self._setup_kmodel()
        self._setup_layouts()
        self._setup_group_switch_option()
        
        self._vbox.show()

    def _setup_kmodel(self):
        separator_kmodel = gtk.HSeparator()
        self._vbox.pack_start(separator_kmodel, expand=False)
        separator_kmodel.show_all()

        label_kmodel = gtk.Label(_('Keyboard Model'))
        label_kmodel.set_alignment(0, 0)
        self._vbox.pack_start(label_kmodel, expand=False)
        label_kmodel.show_all()

        box_kmodel = gtk.VBox()
        box_kmodel.set_border_width(style.DEFAULT_SPACING * 2)
        box_kmodel.set_spacing(style.DEFAULT_SPACING)

        self._kmodel_store = gtk.ListStore(gobject.TYPE_STRING, gobject.TYPE_STRING)
        for description, name in self._xkb.get_models():
            self._kmodel_store.append([name, description])

        self._kmodel_combo = gtk.ComboBox(model = self._kmodel_store)
        cell = gtk.CellRendererText()
        self._kmodel_combo.pack_start(cell)
        self._kmodel_combo.add_attribute(cell, 'text', 1)

        self._kmodel = self._xkb.get_current_model()
        for row in self._kmodel_store:
            if self._kmodel in row[0]:
                self._kmodel_combo.set_active_iter(row.iter)
                break

        box_kmodel.pack_start(self._kmodel_combo, expand = False)
        self._vbox.pack_start(box_kmodel, expand=False)
        box_kmodel.show_all()

        self._kmodel_combo.connect('changed', self.__kmodel_changed_cb)

    def __kmodel_changed_cb(self, combobox):
        if self.__kmodel_sid is not None:
            gobject.source_remove(self.__kmodel_sid)
        self.__kmodel_sid = gobject.timeout_add(_APPLY_TIMEOUT, 
            self.__kmodel_timeout_cb, combobox)

    def __kmodel_timeout_cb(self, combobox):
        it = combobox.get_active_iter()
        model = combobox.get_model()
        self._selected_kmodel = model.get(it, 0)[0]
        if self._selected_kmodel == self._xkb.get_current_model():
            return
        try:
            self._xkb.set_model(self._selected_kmodel)
        except:
            pass #TODO: Show error

        return False

    def _setup_group_switch_option(self):
        separator_grp_option = gtk.HSeparator()
        self._vbox.pack_start(separator_grp_option, expand=False)
        separator_grp_option.show_all()

        label_grp_option = gtk.Label(_('Key(s) to change layout'))
        label_grp_option.set_alignment(0, 0)
        self._vbox.pack_start(label_grp_option, expand=False)
        label_grp_option.show_all()

        box_grp_option = gtk.VBox()
        box_grp_option.set_border_width(style.DEFAULT_SPACING * 2)
        box_grp_option.set_spacing(style.DEFAULT_SPACING)

        self._grp_option_store = gtk.ListStore(gobject.TYPE_STRING, gobject.TYPE_STRING)
        for description, name in self._xkb.get_options_grp():
            self._grp_option_store.append([name, description])

        self._grp_option_combo = gtk.ComboBox(model = self._grp_option_store)
        cell = gtk.CellRendererText()
        self._grp_option_combo.pack_start(cell)
        self._grp_option_combo.add_attribute(cell, 'text', 1)

        self._group_switch_option = self._xkb.get_current_option_grp()
        if not self._group_switch_option:
            self._grp_option_combo.set_active(0)
        else:
            found = False
            for row in self._grp_option_store:
                if self._group_switch_option in row[0]:
                    self._grp_option_combo.set_active_iter(row.iter)
                    found = True
                    break
            if not found:
                self._grp_option_combo.set_active(0)

        box_grp_option.pack_start(self._grp_option_combo, expand = False)
        self._vbox.pack_start(box_grp_option, expand=False)
        box_grp_option.show_all()

        self._grp_option_combo.connect('changed', self.__group_switch_changed_cb)

    def __group_switch_changed_cb(self, combobox):
        if self.__group_switch_sid is not None:
            gobject.source_remove(self.__group_switch_sid)
        self.__group_switch_sid = gobject.timeout_add(_APPLY_TIMEOUT, 
            self.__group_switch_timeout_cb, combobox)

    def __group_switch_timeout_cb(self, combobox):
        it = combobox.get_active_iter()
        model = combobox.get_model()
        self._selected_group_switch_option = model.get(it, 0)[0]
        if self._selected_group_switch_option == \
                self._xkb.get_current_option_grp():
            return
        try:
            self._xkb.set_option_grp(self._selected_group_switch_option)
        except:
            pass #TODO: Show error

        return False

    def _setup_layouts(self):
        separator_klayout = gtk.HSeparator()
        self._vbox.pack_start(separator_klayout, expand=False)
        separator_klayout.show_all()

        label_klayout = gtk.Label(_('Keyboard Layout(s)'))
        label_klayout.set_alignment(0, 0)
        label_klayout.show_all()
        self._vbox.pack_start(label_klayout, expand=False)

        self._klayouts = self._xkb.get_current_layouts()
        for i in range(0, self._xkb.get_max_layouts()):
            add_remove_box = self.__create_add_remove_box()
            self._layout_addremovebox_list.append(add_remove_box)
            self._layout_table.attach(add_remove_box, 1, 2, i, i+1)

            layout_combo = LayoutCombo(self._xkb, i)
            layout_combo.connect('selection-changed', \
                self.__layout_combo_selection_changed_cb)
            self._layout_combo_list.append(layout_combo)
            self._layout_table.attach(layout_combo, 0, 1, i, i+1)

            if i < len(self._klayouts):
                layout_combo.show_all()
                layout_combo.select_layout(self._klayouts[i])
        
        self._vbox.pack_start(self._layout_table, expand=False)
        self._layout_table.set_size_request(self._vbox.size_request()[0], -1)
        self._layout_table.show()
        self._update_klayouts()

    def __determine_add_remove_box_visibility(self):
        i = 1
        for box in self._layout_addremovebox_list:
            if not i == len(self._selected_klayouts):
                box.props.visible = False
            else:
                box.show_all()
                if i == 1:
                    # First row - no need for showing remove btn
                    add, remove = box.get_children()
                    remove.props.visible = False
                if i == self._xkb.get_max_layouts():
                    # Last row - no need for showing add btn
                    add, remove = box.get_children()
                    add.props.visible = False
            i += 1

    def __create_add_remove_box(self):
        '''Creates gtk.Hbox with add/remove buttons'''
        add_icon =  Icon(icon_name='list-add')

        add_button = gtk.Button()
        add_button.set_image(add_icon)
        add_button.connect('clicked',
                            self.__add_button_clicked_cb)

        remove_icon =  Icon(icon_name='list-remove')
        remove_button = gtk.Button()
        remove_button.set_image(remove_icon)
        remove_button.connect('clicked',
                            self.__remove_button_clicked_cb)

        add_remove_box = gtk.HButtonBox()
        add_remove_box.set_layout(gtk.BUTTONBOX_START)
        add_remove_box.set_spacing(10)
        add_remove_box.pack_start(add_button)
        add_remove_box.pack_start(remove_button)

        return add_remove_box

    def __layout_combo_selection_changed_cb(self, combo, layout, index):
        self._update_klayouts()

    def __add_button_clicked_cb(self, button):
        self._layout_combo_list[len(self._selected_klayouts)].show_all()
        self._update_klayouts()
    
    def __remove_button_clicked_cb(self, button):
        self._layout_combo_list[len(self._selected_klayouts) - 1].hide()
        self._update_klayouts()

    def _update_klayouts(self):
        self._selected_klayouts = []
        for combo in self._layout_combo_list:
            if combo.props.visible:
                self._selected_klayouts.append(combo.get_layout())

        self.__determine_add_remove_box_visibility()

        if self.__layout_sid is not None:
            gobject.source_remove(self.__layout_sid)
        self.__layout_sid = gobject.timeout_add(_APPLY_TIMEOUT, 
            self.__layout_timeout_cb)

    def __layout_timeout_cb(self):
        if self._selected_klayouts == self._xkb.get_current_layouts():
            return
        try:
            self._xkb.set_layouts(self._selected_klayouts)
        except:
            pass #TODO: Show error

        return False


    def undo(self):
        self._xkb.set_model(self._kmodel)
        self._xkb.set_layouts(self._klayouts)
        self._xkb.set_option_grp(self._group_switch_option)

