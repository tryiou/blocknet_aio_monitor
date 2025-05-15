import os

import customtkinter as ctk

import custom_tk_mods.ctkCheckBox as ctkCheckBoxMod
import widgets_strings
from config.conf_data import xlite_bin_path, blockdx_bin_path, blocknet_bin_path
from utilities import utils, global_variables


class BinaryFrameManager:
    def __init__(self, parent, master_frame, title_frame):
        self.root = parent.parent
        self.parent = parent
        self.master_frame = master_frame
        self.title_frame = title_frame
        self.tooltip_manager = self.root.tooltip_manager

        self.header_label = ctk.CTkLabel(self.title_frame,
                                         text="Binaries Control panel:")
        self.title_frame.columnconfigure(1, weight=1)

        self.found_label = ctk.CTkLabel(self.title_frame,
                                        text="Found:",
                                        anchor='s')

        self.button_switch_theme = ctk.CTkButton(self.title_frame,
                                                 image=self.root.theme_img,
                                                 command=self.root.switch_theme_command,
                                                 text='',
                                                 fg_color='transparent',
                                                 hover=False,
                                                 width=1)

        # Creating labels
        self.blocknet_label = ctk.CTkLabel(self.master_frame, text="Blocknet Core:")
        self.blockdx_label = ctk.CTkLabel(self.master_frame, text="Block-DX:")
        self.xlite_label = ctk.CTkLabel(self.master_frame, text="Xlite:")
        self.blocknet_installed_boolvar = ctk.BooleanVar(value=False)
        self.blockdx_installed_boolvar = ctk.BooleanVar(value=False)
        self.xlite_installed_boolvar = ctk.BooleanVar(value=False)

        self.blocknet_version_optionmenu = ctk.CTkOptionMenu(self.master_frame,
                                                             values=self.root.blocknet_manager.blocknet_version,
                                                             state='disabled')
        self.blockdx_version_optionmenu = ctk.CTkOptionMenu(self.master_frame,
                                                            values=self.root.blockdx_manager.version,
                                                            state='disabled')
        self.xlite_version_optionmenu = ctk.CTkOptionMenu(self.master_frame,
                                                          values=self.root.xlite_manager.xlite_version,
                                                          state='disabled')
        self.blocknet_found_checkbox = ctkCheckBoxMod.CTkCheckBox(self.master_frame,
                                                                  text='',
                                                                  variable=self.blocknet_installed_boolvar,
                                                                  state='disabled',
                                                                  corner_radius=25, width=1)
        self.blockdx_found_checkbox = ctkCheckBoxMod.CTkCheckBox(self.master_frame,
                                                                 text='',
                                                                 variable=self.blockdx_installed_boolvar,
                                                                 state='disabled',
                                                                 corner_radius=25)
        self.xlite_found_checkbox = ctkCheckBoxMod.CTkCheckBox(self.master_frame,
                                                               text='',
                                                               variable=self.xlite_installed_boolvar,
                                                               state='disabled',
                                                               corner_radius=25)
        bin_button_width = 90
        self.install_delete_blocknet_string_var = ctk.StringVar(value='')
        self.install_delete_blocknet_button = ctk.CTkButton(self.master_frame,
                                                            state='normal',
                                                            image=self.root.transparent_img,
                                                            command=self.parent.install_delete_blocknet_command,
                                                            # text="",
                                                            width=bin_button_width,
                                                            textvariable=self.install_delete_blocknet_string_var,
                                                            corner_radius=25)
        self.install_delete_blockdx_string_var = ctk.StringVar(value='')
        self.install_delete_blockdx_button = ctk.CTkButton(self.master_frame,
                                                           state='normal',
                                                           image=self.root.transparent_img,
                                                           command=self.parent.install_delete_blockdx_command,
                                                           textvariable=self.install_delete_blockdx_string_var,
                                                           width=bin_button_width,
                                                           # text="",
                                                           corner_radius=25)
        self.install_delete_xlite_string_var = ctk.StringVar(value='')
        self.install_delete_xlite_button = ctk.CTkButton(self.master_frame,
                                                         state='normal',
                                                         image=self.root.transparent_img,
                                                         command=self.parent.install_delete_xlite_command,
                                                         textvariable=self.install_delete_xlite_string_var,
                                                         width=bin_button_width,
                                                         # text="",
                                                         corner_radius=25)
        self.blocknet_start_close_button_string_var = ctk.StringVar(value='')
        self.blocknet_start_close_button = ctk.CTkButton(self.master_frame,
                                                         image=self.root.transparent_img,
                                                         # textvariable=self.blocknet_start_close_button_string_var,
                                                         width=bin_button_width,
                                                         text="",
                                                         command=self.parent.start_or_close_blocknet,
                                                         corner_radius=25)
        self.blockdx_start_close_button_string_var = ctk.StringVar(value='')
        self.blockdx_start_close_button = ctk.CTkButton(self.master_frame,
                                                        image=self.root.transparent_img,
                                                        # textvariable=self.blockdx_start_close_button_string_var,
                                                        width=bin_button_width,
                                                        text="",
                                                        command=self.parent.start_or_close_blockdx,
                                                        corner_radius=25)
        self.xlite_start_close_button_string_var = ctk.StringVar(value='')
        self.xlite_start_close_button = ctk.CTkButton(self.master_frame,
                                                      image=self.root.transparent_img,
                                                      # textvariable=self.xlite_start_close_button_string_var,
                                                      width=bin_button_width,
                                                      text="",
                                                      command=self.parent.start_or_close_xlite,
                                                      corner_radius=25)

    def update_blocknet_start_close_button(self):
        var = widgets_strings.close_string if self.root.blocknet_manager.blocknet_process_running else widgets_strings.start_string
        self.blocknet_start_close_button_string_var.set(var)

        if self.root.blocknet_manager.blocknet_process_running:
            self.tooltip_manager.update_tooltip(self.blocknet_start_close_button, widgets_strings.close_string)
        else:
            self.tooltip_manager.update_tooltip(self.blocknet_start_close_button, widgets_strings.start_string)

        enabled = (not self.root.blocknet_manager.utility.downloading_bin and
                   not self.parent.disable_start_blocknet_button and
                   not self.root.blocknet_manager.utility.bootstrap_checking)
        if enabled:
            img = self.root.stop_img if self.root.blocknet_manager.blocknet_process_running else self.root.start_img
            utils.enable_button(self.blocknet_start_close_button, img=img)
        else:
            img = self.root.stop_greyed_img if self.root.blocknet_manager.blocknet_process_running else self.root.start_greyed_img
            utils.disable_button(self.blocknet_start_close_button, img=img)

    def grid_widgets(self, x, y):
        # bin
        self.header_label.grid(row=x, column=y, padx=5, pady=0, sticky="nw")
        self.button_switch_theme.grid(row=x, column=y + 5, padx=2, pady=2, sticky='e')
        self.blocknet_label.grid(row=x + 1, column=y, padx=5, pady=2, sticky="e")
        self.blockdx_label.grid(row=x + 2, column=y, padx=5, pady=2, sticky="e")
        self.xlite_label.grid(row=x + 3, column=y, padx=5, pady=(2, 5), sticky="e")
        sticky = 'ew'
        self.blocknet_version_optionmenu.grid(row=x + 1, column=y + 1, padx=5, sticky=sticky)
        self.blockdx_version_optionmenu.grid(row=x + 2, column=y + 1, padx=5, sticky=sticky)
        self.xlite_version_optionmenu.grid(row=x + 3, column=y + 1, padx=5, pady=(2, 5), sticky=sticky)
        self.blocknet_found_checkbox.grid(row=x + 1, column=y + 2, padx=5, sticky=sticky)
        self.blockdx_found_checkbox.grid(row=x + 2, column=y + 2, padx=5, sticky=sticky)
        self.xlite_found_checkbox.grid(row=x + 3, column=y + 2, padx=5, pady=(2, 5), sticky=sticky)
        button_sticky = 'ew'
        padx_main_frame = (70, 8)
        self.install_delete_blocknet_button.grid(row=x + 1, column=y + 3, padx=padx_main_frame,
                                                 sticky=button_sticky)
        self.install_delete_blockdx_button.grid(row=x + 2, column=y + 3, padx=padx_main_frame,
                                                sticky=button_sticky)
        self.install_delete_xlite_button.grid(row=x + 3, column=y + 3, padx=padx_main_frame, pady=(2, 5),
                                              sticky=button_sticky)
        padx_main_frame = (8, 8)
        self.blocknet_start_close_button.grid(row=x + 1, column=y + 4, padx=padx_main_frame, sticky='e')
        # Button for starting or closing Block-dx
        self.blockdx_start_close_button.grid(row=x + 2, column=y + 4, padx=padx_main_frame, sticky='e')
        # Button for starting or closing Xlite
        self.xlite_start_close_button.grid(row=x + 3, column=y + 4, padx=padx_main_frame, pady=(2, 5), sticky='e')

    def update_blockdx_start_close_button(self):
        # blockdx_start_close_button_string_var
        var = widgets_strings.close_string if self.root.blockdx_manager.process_running else widgets_strings.start_string
        self.blockdx_start_close_button_string_var.set(var)

        enabled = (self.root.blockdx_manager.process_running or (
                not self.root.blockdx_manager.utility.downloading_bin and
                self.root.blocknet_manager.utility.valid_rpc) and
                   not self.parent.disable_start_blockdx_button)
        if enabled:
            if self.root.blockdx_manager.process_running:
                self.tooltip_manager.update_tooltip(self.blockdx_start_close_button, msg=widgets_strings.close_string)
                img = self.root.stop_img
            else:
                self.tooltip_manager.update_tooltip(self.blockdx_start_close_button, msg=widgets_strings.start_string)
                img = self.root.start_img
            utils.enable_button(self.blockdx_start_close_button, img=img)

            # self.blockdx_start_close_button_tooltip.hide()
        else:
            if self.root.blockdx_manager.process_running:
                img = self.root.stop_greyed_img
                self.tooltip_manager.update_tooltip(self.blockdx_start_close_button,
                                                    msg=widgets_strings.close_string)
            else:
                self.tooltip_manager.update_tooltip(self.blockdx_start_close_button,
                                                    msg=widgets_strings.blockdx_missing_blocknet_config_string)
                img = self.root.start_greyed_img
            utils.disable_button(self.blockdx_start_close_button, img=img)

    async def coroutine_update_bins_buttons(self):

        self.update_blocknet_start_close_button()
        self.update_blockdx_start_close_button()
        self.update_xlite_start_close_button()

        blocknet_boolvar = self.blocknet_installed_boolvar.get()
        blockdx_boolvar = self.blockdx_installed_boolvar.get()
        xlite_boolvar = self.xlite_installed_boolvar.get()

        percent_buff = self.root.blocknet_manager.utility.binary_percent_download
        dl_string = f"{int(percent_buff)}%" if percent_buff else ""
        var_blocknet = dl_string if self.root.blocknet_manager.utility.downloading_bin else ""
        blocknet_folder = os.path.join(global_variables.aio_folder, blocknet_bin_path[0])

        if blocknet_boolvar:
            var_blocknet = ""
            self.tooltip_manager.update_tooltip(self.install_delete_blocknet_button, blocknet_folder)
            button_condition = self.root.blocknet_manager.blocknet_process_running or self.root.blocknet_manager.utility.downloading_bin
        else:
            self.tooltip_manager.update_tooltip(self.install_delete_blocknet_button,
                                                global_variables.blocknet_release_url)
            button_condition = self.root.blocknet_manager.utility.downloading_bin

        if button_condition:
            utils.disable_button(self.install_delete_blocknet_button,
                                 img=self.root.delete_greyed_img if blocknet_boolvar else self.root.install_greyed_img)
        else:
            utils.enable_button(self.install_delete_blocknet_button,
                                img=self.root.delete_img if blocknet_boolvar else self.root.install_img)

        percent_buff = self.root.blockdx_manager.utility.binary_percent_download
        dl_string = f"{int(percent_buff)}%" if percent_buff else ""
        var_blockdx = dl_string if self.root.blockdx_manager.utility.downloading_bin else ""
        blockdx_folder = os.path.join(global_variables.aio_folder, blockdx_bin_path.get(global_variables.system))

        if blockdx_boolvar:
            var_blockdx = ""
            self.tooltip_manager.update_tooltip(self.install_delete_blockdx_button, blockdx_folder)
            button_condition = self.root.blockdx_manager.process_running or self.root.blockdx_manager.utility.downloading_bin
        else:
            self.tooltip_manager.update_tooltip(self.install_delete_blockdx_button,
                                                global_variables.blockdx_release_url)
            button_condition = self.root.blockdx_manager.utility.downloading_bin

        if button_condition:
            utils.disable_button(self.install_delete_blockdx_button,
                                 img=self.root.delete_greyed_img if blockdx_boolvar else self.root.install_greyed_img)
        else:
            utils.enable_button(self.install_delete_blockdx_button,
                                img=self.root.delete_img if blockdx_boolvar else self.root.install_img)

        percent_buff = self.root.xlite_manager.utility.binary_percent_download
        dl_string = f"{int(percent_buff)}%" if percent_buff else ""
        var_xlite = dl_string if self.root.xlite_manager.utility.downloading_bin else ""
        folder = os.path.join(global_variables.aio_folder, xlite_bin_path.get(global_variables.system))

        if xlite_boolvar:
            var_xlite = ""
            self.tooltip_manager.update_tooltip(self.install_delete_xlite_button, folder)
            button_condition = self.root.xlite_manager.process_running or self.root.xlite_manager.utility.downloading_bin
        else:
            self.tooltip_manager.update_tooltip(self.install_delete_xlite_button,
                                                global_variables.xlite_release_url)
            button_condition = self.root.xlite_manager.utility.downloading_bin

        if button_condition:
            utils.disable_button(self.install_delete_xlite_button,
                                 img=self.root.delete_greyed_img if xlite_boolvar else self.root.install_greyed_img)
        else:
            utils.enable_button(self.install_delete_xlite_button,
                                img=self.root.delete_img if xlite_boolvar else self.root.install_img)

        self.install_delete_blocknet_string_var.set(var_blocknet)
        self.install_delete_blockdx_string_var.set(var_blockdx)
        self.install_delete_xlite_string_var.set(var_xlite)

    def update_xlite_start_close_button(self):
        # xlite_start_close_button_string_var
        var = widgets_strings.close_string if self.root.xlite_manager.process_running else widgets_strings.start_string
        self.xlite_start_close_button_string_var.set(var)

        if self.root.xlite_manager.process_running:
            self.tooltip_manager.update_tooltip(self.xlite_start_close_button, widgets_strings.close_string)
        else:
            self.tooltip_manager.update_tooltip(self.xlite_start_close_button, widgets_strings.start_string)

        # xlite_start_close_button
        disable_start_close_button = self.root.xlite_manager.utility.downloading_bin or self.parent.disable_start_xlite_button

        if not disable_start_close_button:
            img = self.root.stop_img if self.root.xlite_manager.process_running else self.root.start_img
            # self.xlite_start_close_button.configure(image=img)
            utils.enable_button(self.xlite_start_close_button, img=img)
        else:
            img = self.root.stop_greyed_img if self.root.xlite_manager.process_running else self.root.start_greyed_img
            utils.disable_button(self.xlite_start_close_button, img=img)
