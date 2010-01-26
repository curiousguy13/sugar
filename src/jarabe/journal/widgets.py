# Copyright (C) 2006, Red Hat, Inc.
# Copyright (C) 2007, One Laptop Per Child
# Copyright (C) 2010, Aleksey Lim
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
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

import logging
from gettext import gettext as _

import gtk
import gobject
import gconf
import simplejson

from sugar.graphics import style
from sugar.graphics.xocolor import XoColor
from sugar.graphics.palette import Invoker
from sugar.graphics.palette import WidgetInvoker
from sugar.graphics.icon import Icon
from sugar.graphics.icon import get_surface

from jarabe.journal.entry import Entry
from jarabe.journal.palettes import BuddyPalette
from jarabe.journal.palettes import ObjectPalette
from jarabe.journal import misc
from jarabe.journal import model
from jarabe.journal import controler
from jarabe.journal import preview


class _Button(gtk.Alignment):

    def __init__(self, **kwargs):
        gtk.Alignment.__init__(self, xalign=0.5, yalign=0.5, xscale=0, yscale=0)

        self.metadata = None
        self.prelight = False

        self.set_size_request(style.GRID_CELL_SIZE, -1)

        box = gtk.EventBox()
        box.props.visible_window = False
        box.show()
        self.add(box)

        self.icon = Icon(**kwargs)
        self.icon.show()
        box.add(self.icon)

        box.connect('enter-notify-event', self.__enter_notify_event_cb)
        box.connect('leave-notify-event', self.__leave_notify_event_cb)
        box.connect('button-release-event', self.__button_release_event_cb)

        self.do_colors()

    def fill_in(self, metadata):
        self.metadata = metadata

    def do_activate(self):
        # stub
        pass

    def do_colors(self):
        if self.prelight:
            self.icon.props.fill_color = style.COLOR_BLACK.get_svg()
        else:
            self.icon.props.fill_color = style.COLOR_BUTTON_GREY.get_svg()

    def __enter_notify_event_cb(self, widget, event):
        self.prelight = True
        self.do_colors()

    def __leave_notify_event_cb(self, widget, event):
        self.prelight = False
        self.do_colors()

    def __button_release_event_cb(self, widget, event):
        if self.prelight:
            self.do_activate()


class KeepIcon(_Button):

    def __init__(self):
        self._keep_color = None

        _Button.__init__(self,
                icon_name='emblem-favorite',
                pixel_size=style.SMALL_ICON_SIZE)

    def fill_in(self, metadata):
        _Button.fill_in(self, metadata)

        keep = metadata.get('keep', "")
        if keep.isdigit():
            self._set_keep(int(keep))
        else:
            self._set_keep(0)

    def do_colors(self):
        if self.prelight:
            if self._keep_color is None:
                self.icon.props.stroke_color = \
                        style.COLOR_BUTTON_GREY.get_svg()
                self.icon.props.fill_color = style.COLOR_BUTTON_GREY.get_svg()
            else:
                stroke_color = style.Color(self._keep_color.get_stroke_color())
                fill_color = style.Color(self._keep_color.get_fill_color())
                self.icon.props.stroke_color = fill_color.get_svg()
                self.icon.props.fill_color = stroke_color.get_svg()
        else:
            if self._keep_color is None:
                self.icon.props.stroke_color = \
                        style.COLOR_BUTTON_GREY.get_svg()
                self.icon.props.fill_color = style.COLOR_TRANSPARENT.get_svg()
            else:
                self.icon.props.xo_color = self._keep_color

    def do_activate(self):
        if not model.is_editable(self.metadata):
            return

        if self._keep_color is None:
            keep = 1
        else:
            keep = 0

        self.metadata['keep'] = keep
        model.write(self.metadata, update_mtime=False)

        self._set_keep(keep)

    def _set_keep(self, keep):
        if keep:
            client = gconf.client_get_default()
            color = client.get_string('/desktop/sugar/user/color')
            self._keep_color = XoColor(color)
        else:
            self._keep_color = None

        self.do_colors()


class _JournalObject(gtk.EventBox):

    def __init__(self, detail, paint_box):
        gtk.EventBox.__init__(self)

        self.metadata = None
        self._detail = detail

        self._invoker = WidgetInvoker(self)
        self._invoker._position_hint = Invoker.AT_CURSOR

        self.modify_fg(gtk.STATE_NORMAL,
                style.COLOR_PANEL_GREY.get_gdk_color())
        self.modify_bg(gtk.STATE_NORMAL,
                style.COLOR_WHITE.get_gdk_color())

        self.connect_after('button-release-event',
                self.__button_release_event_cb)

        self.connect('destroy', self.__destroy_cb)
        if paint_box:
            self.connect_after('expose-event', self.__expose_event_cb)

        # DND stuff

        self._drag = False
        self._temp_drag_file_path = None
        self.drag_source_set(gtk.gdk.BUTTON1_MASK,
                [('text/uri-list', 0, 0), ('journal-object-id', 0, 0)],
                gtk.gdk.ACTION_COPY)
        self.connect('drag-begin', self.__drag_begin_cb)
        self.connect('drag-data-get', self.__drag_data_get_cb)
        self.connect('drag-end', self.__drag_end_cb)

    def fill_in(self, metadata):
        self.metadata = metadata
        self._invoker.palette = None

    def create_palette(self):
        if self.metadata is not None:
            return ObjectPalette(self.metadata, detail=self._detail)

    def __destroy_cb(self, icon):
        if self._invoker is not None:
            self._invoker.detach()

    def __expose_event_cb(self, widget, event):
        __, __, width, height = self.allocation
        fg = self.style.fg_gc[gtk.STATE_NORMAL]
        self.window.draw_rectangle(fg, False, 0, 0, width - 1, height - 1)

    def __drag_begin_cb(self, widget, context):
        self._drag = True

        if self._invoker.palette is not None:
            self._invoker.palette.popdown(immediate=True)

        surface = get_surface(
                file_name=misc.get_icon_name(self.metadata),
                xo_color=misc.get_icon_color(self.metadata))
        pixmap, bitmask = _surface_to_pixels(self.window, surface)

        context.set_icon_pixmap(self.get_colormap(), pixmap, bitmask,
                surface.get_width() / 2, surface.get_height() / 2)

    def __drag_data_get_cb(self, widget, context, selection, target_type,
            event_time):
        if selection.target == 'text/uri-list':
            # Get hold of a reference so the temp file doesn't get deleted
            self._temp_drag_file_path = model.get_file(self.metadata)
            logging.debug('putting %r in selection', self._temp_drag_file_path)
            selection.set(selection.target, 8, self._temp_drag_file_path)

        elif selection.target == 'journal-object-id':
            selection.set(selection.target, 8, self.metadata['uid'])

    def __drag_end_cb(self, widget, context):
        self._drag = False
        self._temp_drag_file_path = None

    def __button_release_event_cb(self, button, event):
        if not self._drag and self.metadata is not None:
            misc.resume(self.metadata)
        return True


class ObjectIcon(_JournalObject):

    def __init__(self, detail=True, paint_box=True, **kwargs):
        _JournalObject.__init__(self, detail, paint_box)

        self._icon = Icon(**kwargs)
        self._icon.show()
        self.add(self._icon)

    def fill_in(self, metadata):
        _JournalObject.fill_in(self, metadata)
        self._icon.props.file = misc.get_icon_name(metadata)
        self._icon.props.xo_color = misc.get_icon_color(metadata)


class Thumb(_JournalObject):

    def __init__(self, detail=True, paint_box=True):
        _JournalObject.__init__(self, detail, paint_box)

        self._image = gtk.Image()
        self._image.show()
        self.add(self._image)

    def set_from_pixbuf(self, pixbuf):
        self._image.set_from_pixbuf(pixbuf)


class Title(Entry):

    def __init__(self, **kwargs):
        Entry.__init__(self, **kwargs)

        self.metadata = None

        self.connect_after('focus-out-event', self.__focus_out_event_cb)

    def fill_in(self, metadata):
        self.metadata = metadata
        self.props.text = metadata.get('title', _('Untitled'))
        self.props.editable = model.is_editable(metadata)

    def __focus_out_event_cb(self, widget, event):
        old_title = self.metadata.get('title', None)
        new_title = self.props.text

        if old_title != new_title:
            self.metadata['title'] = new_title
            self.metadata['title_set_by_user'] = '1'
            model.write(self.metadata, update_mtime=False)


class Buddies(gtk.Alignment):

    def __init__(self, buddies_max=None, **kwargs):
        gtk.Alignment.__init__(self, **kwargs)

        self._buddies_max = buddies_max

        self._progress = gtk.ProgressBar()
        self._progress.modify_bg(gtk.STATE_INSENSITIVE,
                style.COLOR_WHITE.get_gdk_color())
        self._progress.show()

        self._buddies = gtk.HBox()
        self._buddies.show()

    def fill_in(self, metadata):
        if self.child is not None:
            self.remove(self.child)

        child = None

        if 'progress' in metadata:
            child = self._progress
            fraction = int(metadata['progress']) / 100.
            self._progress.props.fraction = fraction

        elif 'buddies' in metadata and metadata['buddies']:
            child = self._buddies

            buddies = simplejson.loads(metadata['buddies']).values()
            buddies = buddies[:self._buddies_max]

            def show(icon, buddy):
                icon.set_buddy(buddy)
                icon.show()

            for icon in self._buddies:
                if buddies:
                    show(icon, buddies.pop())
                else:
                    icon.hide()

            for buddy in buddies:
                icon = _BuddyIcon()
                show(icon, buddy)
                self._buddies.add(icon)

        if self.child is not child:
            if self.child is not None:
                self.remove(self.child)
            if child is not None:
                self.add(child)


class Timestamp(gtk.Label):

    def __init__(self, **kwargs):
        gobject.GObject.__init__(self, **kwargs)
        self.props.selectable = True

    def fill_in(self, metadata):
        self.props.label = misc.get_date(metadata)


class DetailsIcon(_Button):
    def __init__(self):
        _Button.__init__(self,
                icon_name='go-right',
                pixel_size=style.SMALL_ICON_SIZE,
                stroke_color=style.COLOR_TRANSPARENT.get_svg())

    def do_activate(self):
        self.prelight = False
        self.do_colors()
        controler.details.send(None, uid=self.metadata['uid'])


class _BuddyIcon(gtk.EventBox):

    def __init__(self):
        gtk.EventBox.__init__(self)

        self.buddy = None

        self.props.visible_window = False

        self._icon = Icon(
                icon_name='computer-xo',
                pixel_size=style.STANDARD_ICON_SIZE)
        self._icon.show()
        self.add(self._icon)

        self._invoker = WidgetInvoker(self)
        self._invoker._position_hint = Invoker.AT_CURSOR

        self.connect('destroy', self.__destroy_cb)

    def set_buddy(self, buddy):
        self.buddy = buddy
        self._invoker.palette = None
        nick_, color = buddy
        self._icon.props.xo_color = XoColor(color)

    def create_palette(self):
        return BuddyPalette(self.buddy)

    def __destroy_cb(self, icon):
        if self._invoker is not None:
            self._invoker.detach()


def _surface_to_pixels(drawable, surface):
    width = surface.get_width()
    height = surface.get_height()

    pixmap = gtk.gdk.Pixmap(drawable, width, height)
    pixmap_context = pixmap.cairo_create()
    pixmap_context.set_source_surface(surface)
    pixmap_context.paint();

    mask_row_size = (width + 7) / 8
    mask_size = height * mask_row_size
    mask_data = '\x00' * mask_size
    mask = gtk.gdk.bitmap_create_from_data(drawable, mask_data, width, height)
    mask_context = mask.cairo_create()
    mask_context.set_source_surface(surface)
    mask_context.paint();

    return pixmap, mask