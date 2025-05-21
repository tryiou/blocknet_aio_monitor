import customtkinter as ctk

import custom_tk_mods.ctkCheckBox as ctkCheckBoxMod
import utilities.utils
from gui.constants import HEADER_FRAMES_STICKY, CORNER_RADIUS, BINS_BUTTONS_WIDTH, BINS_FRAME_WIDTH
from gui.xbridge_bot_manager import XBridgeBotManager


class BinaryFrameManager:
    def __init__(self, parent, master_frame, title_frame):
        self.root_gui = parent.root_gui
        self.parent = parent
        self.master_frame = master_frame
        self.title_frame = title_frame
        self.xbridge_bot_manager = XBridgeBotManager()

        self.header_label = ctk.CTkLabel(self.title_frame,
                                         text="Binaries Control panel:",
                                         anchor=HEADER_FRAMES_STICKY,
                                         width=BINS_FRAME_WIDTH)
        self.title_frame.columnconfigure(1, weight=1)

        self.found_label = ctk.CTkLabel(self.title_frame,
                                        text="Found:",
                                        anchor='s')

        self.button_switch_theme = ctk.CTkButton(self.title_frame,
                                                 image=self.root_gui.theme_img,
                                                 command=self.root_gui.switch_theme_command,
                                                 text='',
                                                 fg_color='transparent',
                                                 hover=False,
                                                 width=1)

        # Bins labels
        self.blocknet_label = ctk.CTkLabel(self.master_frame, text="Blocknet Core:")
        self.blockdx_label = ctk.CTkLabel(self.master_frame, text="Block-DX:")
        self.xlite_label = ctk.CTkLabel(self.master_frame, text="Xlite:")
        self.bots_label = ctk.CTkLabel(self.master_frame, text="XBridge Bots:")

        # Bins option_menus
        option_menu_width = 200
        self.blocknet_version_optionmenu = ctk.CTkOptionMenu(self.master_frame,
                                                             values=self.root_gui.blocknet_manager.version,
                                                             state='disabled',
                                                             width=option_menu_width)
        self.blockdx_version_optionmenu = ctk.CTkOptionMenu(self.master_frame,
                                                            values=self.root_gui.blockdx_manager.version,
                                                            state='disabled',
                                                            width=option_menu_width)
        self.xlite_version_optionmenu = ctk.CTkOptionMenu(self.master_frame,
                                                          values=self.root_gui.xlite_manager.version,
                                                          state='disabled',
                                                          width=option_menu_width)
        self.bots_version_optionmenu = ctk.CTkOptionMenu(self.master_frame,
                                                         values=self.xbridge_bot_manager.get_available_branches(),
                                                         state='normal',
                                                         width=option_menu_width)
        # Checkboxes BoolVars
        self.blocknet_installed_boolvar = ctk.BooleanVar(value=False)
        self.blockdx_installed_boolvar = ctk.BooleanVar(value=False)
        self.xlite_installed_boolvar = ctk.BooleanVar(value=False)
        self.bots_installed_boolvar = ctk.BooleanVar(value=False)

        # Bins checkboxes
        self.blocknet_found_checkbox = ctkCheckBoxMod.CTkCheckBox(self.master_frame,
                                                                  text='',
                                                                  variable=self.blocknet_installed_boolvar,
                                                                  state='disabled',
                                                                  corner_radius=CORNER_RADIUS, width=1)
        self.blockdx_found_checkbox = ctkCheckBoxMod.CTkCheckBox(self.master_frame,
                                                                 text='',
                                                                 variable=self.blockdx_installed_boolvar,
                                                                 state='disabled',
                                                                 corner_radius=CORNER_RADIUS)
        self.xlite_found_checkbox = ctkCheckBoxMod.CTkCheckBox(self.master_frame,
                                                               text='',
                                                               variable=self.xlite_installed_boolvar,
                                                               state='disabled',
                                                               corner_radius=CORNER_RADIUS)
        self.bots_found_checkbox = ctkCheckBoxMod.CTkCheckBox(self.master_frame,
                                                              text='',
                                                              variable=self.bots_installed_boolvar,
                                                              state='disabled',
                                                              corner_radius=CORNER_RADIUS)
        # install/delete buttons
        # bin_button_width = 90
        self.install_delete_blocknet_string_var = ctk.StringVar(value='')
        self.install_delete_blocknet_button = ctk.CTkButton(self.master_frame,
                                                            state='normal',
                                                            image=self.root_gui.transparent_img,
                                                            command=self.parent.install_delete_blocknet_command,
                                                            # text="",
                                                            width=BINS_BUTTONS_WIDTH,
                                                            textvariable=self.install_delete_blocknet_string_var,
                                                            corner_radius=CORNER_RADIUS)
        self.install_delete_blockdx_string_var = ctk.StringVar(value='')
        self.install_delete_blockdx_button = ctk.CTkButton(self.master_frame,
                                                           state='normal',
                                                           image=self.root_gui.transparent_img,
                                                           command=self.parent.install_delete_blockdx_command,
                                                           textvariable=self.install_delete_blockdx_string_var,
                                                           width=BINS_BUTTONS_WIDTH,
                                                           # text="",
                                                           corner_radius=CORNER_RADIUS)
        self.install_delete_xlite_string_var = ctk.StringVar(value='')
        self.install_delete_xlite_button = ctk.CTkButton(self.master_frame,
                                                         state='normal',
                                                         image=self.root_gui.transparent_img,
                                                         command=self.parent.install_delete_xlite_command,
                                                         textvariable=self.install_delete_xlite_string_var,
                                                         width=BINS_BUTTONS_WIDTH,
                                                         # text="",
                                                         corner_radius=CORNER_RADIUS)
        self.install_delete_bots_button = ctk.CTkButton(self.master_frame,
                                                        state='normal',
                                                        text="",
                                                        image=self.root_gui.transparent_img,
                                                        command=self.install_update_bots_command,
                                                        width=BINS_BUTTONS_WIDTH,
                                                        corner_radius=CORNER_RADIUS)
        # start/close buttons
        self.blocknet_start_close_button_string_var = ctk.StringVar(value='')
        self.blocknet_start_close_button = ctk.CTkButton(self.master_frame,
                                                         image=self.root_gui.transparent_img,
                                                         # textvariable=self.blocknet_start_close_button_string_var,
                                                         width=BINS_BUTTONS_WIDTH,
                                                         text="",
                                                         command=self.parent.start_or_close_blocknet,
                                                         corner_radius=CORNER_RADIUS)
        self.blockdx_start_close_button_string_var = ctk.StringVar(value='')
        self.blockdx_start_close_button = ctk.CTkButton(self.master_frame,
                                                        image=self.root_gui.transparent_img,
                                                        # textvariable=self.blockdx_start_close_button_string_var,
                                                        width=BINS_BUTTONS_WIDTH,
                                                        text="",
                                                        command=self.parent.start_or_close_blockdx,
                                                        corner_radius=CORNER_RADIUS)
        self.xlite_toggle_execution_string_var = ctk.StringVar(value='')
        self.xlite_toggle_execution_button = ctk.CTkButton(self.master_frame,
                                                           image=self.root_gui.transparent_img,
                                                           # textvariable=self.xlite_start_close_button_string_var,
                                                           width=BINS_BUTTONS_WIDTH,
                                                           text="",
                                                           command=self.parent.start_or_close_xlite,
                                                           corner_radius=CORNER_RADIUS)
        self.bots_toggle_execution_button = ctk.CTkButton(self.master_frame,
                                                          image=self.root_gui.transparent_img,
                                                          text="",
                                                          command=self.toggle_bots_execution_command,
                                                          width=BINS_BUTTONS_WIDTH,
                                                          corner_radius=CORNER_RADIUS)

        # Bots buttons

    def install_update_bots_command(self):
        """Handle install/update button click - left click installs/updates, right click deletes"""
        if self.xbridge_bot_manager and self.bots_version_optionmenu.get():
            utilities.utils.disable_button(self.install_delete_bots_button, self.root_gui.install_greyed_img)
            utilities.utils.disable_button(self.bots_toggle_execution_button, self.root_gui.start_greyed_img)
            self.xbridge_bot_manager.install_or_update(self.bots_version_optionmenu.get())

    def toggle_bots_execution_command(self):
        """Handle execution toggle button click"""
        branch = self.bots_version_optionmenu.get()
        if self.xbridge_bot_manager and branch:
            utilities.utils.disable_button(self.install_delete_bots_button, self.root_gui.install_greyed_img)
            utilities.utils.disable_button(self.bots_toggle_execution_button, self.root_gui.start_greyed_img)
            self.xbridge_bot_manager.toggle_execution(branch)

    def grid_widgets(self, x, y):
        # bin
        self.header_label.grid(row=x, column=y, padx=5, pady=5, sticky="nw")
        self.button_switch_theme.grid(row=x, column=y + 5, padx=5, pady=5, sticky='e')
        label_sticky = "e"
        self.blocknet_label.grid(row=x + 1, column=y, padx=5, pady=5, sticky=label_sticky)
        self.blockdx_label.grid(row=x + 2, column=y, padx=5, pady=5, sticky=label_sticky)
        self.xlite_label.grid(row=x + 3, column=y, padx=5, pady=5, sticky=label_sticky)
        self.bots_label.grid(row=x + 4, column=y, padx=5, pady=5, sticky=label_sticky)
        sticky = 'ew'
        self.blocknet_version_optionmenu.grid(row=x + 1, column=y + 1, sticky=sticky)
        self.blockdx_version_optionmenu.grid(row=x + 2, column=y + 1, sticky=sticky)
        self.xlite_version_optionmenu.grid(row=x + 3, column=y + 1, sticky=sticky)
        self.bots_version_optionmenu.grid(row=x + 4, column=y + 1, sticky=sticky)

        self.blocknet_found_checkbox.grid(row=x + 1, column=y + 2, padx=5, sticky=sticky)
        self.blockdx_found_checkbox.grid(row=x + 2, column=y + 2, padx=5, sticky=sticky)
        self.xlite_found_checkbox.grid(row=x + 3, column=y + 2, padx=5, sticky=sticky)
        self.bots_found_checkbox.grid(row=x + 4, column=y + 2, padx=5, sticky=sticky)
        button_sticky = 'ew'
        padx_main_frame = (70, 8)
        # padx_main_frame = 5
        self.install_delete_blocknet_button.grid(row=x + 1, column=y + 3, padx=padx_main_frame, sticky=button_sticky)
        self.install_delete_blockdx_button.grid(row=x + 2, column=y + 3, padx=padx_main_frame, sticky=button_sticky)
        self.install_delete_xlite_button.grid(row=x + 3, column=y + 3, padx=padx_main_frame, sticky=button_sticky)
        self.install_delete_bots_button.grid(row=x + 4, column=y + 3, padx=padx_main_frame, sticky=button_sticky)
        padx_main_frame = (8, 8)
        padx_main_frame = 5
        self.blocknet_start_close_button.grid(row=x + 1, column=y + 4, padx=padx_main_frame, sticky='e')
        # Button for starting or closing Block-dx
        self.blockdx_start_close_button.grid(row=x + 2, column=y + 4, padx=padx_main_frame, sticky='e')
        # Button for starting or closing Xlite
        self.xlite_toggle_execution_button.grid(row=x + 3, column=y + 4, padx=padx_main_frame, sticky='e')
        self.bots_toggle_execution_button.grid(row=x + 4, column=y + 4, padx=padx_main_frame, sticky='e')
