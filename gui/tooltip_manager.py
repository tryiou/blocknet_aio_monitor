import CTkToolTip

from utilities.utils import configure_tooltip_text


class TooltipManager:
    def __init__(self, parent):
        self.parent = parent
        self.tooltips = {}

    def register_tooltip(self, widget, msg, **kwargs):
        tooltip = CTkToolTip.CTkToolTip(widget, message=msg, **kwargs)
        self.tooltips[widget] = tooltip

    def update_tooltip(self, widget, msg):
        if widget in self.tooltips:
            configure_tooltip_text(self.tooltips[widget], msg)
