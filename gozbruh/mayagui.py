"""Class to create a gui within maya uses gozbruh.maya_tools

(Not currently used in the main functionality of the program except for send())
"""
import os
import sys

import pymel.core as pm
from . import maya_tools
from . import utils


class Win(object):
    """GUI for maya_tools

    Attributes
    ----------
    serv : MayaServer
        MayaServer instance
    client : MayaToZBrushClient
        MayaToZBrushClient instance
    user_* : str
        user defined network info
    maya_status_ui : bool
        connection status
    zbrush_status_gui : pymel label
        connection status Label
    """

    def __init__(self):
        """ new server/client, make gui, start server """

        self.serv = maya_tools.MayaServer()
        self.client = maya_tools.MayaToZBrushClient()
        self.gui_window = None
        self.send_btn = None
        self.user_zbrush_host = None
        self.user_zbrush_port = None
        self.listen_btn = None
        self.user_maya_host = None
        self.user_maya_port = None
        self.user_shared_dir = None
        self.maya_status_ui = None
        self.conn_btn = None
        self.zbrush_status_gui = None

        # make the gui
        self.build()
        self.buttons()
        # start MayaServer
        self.listen()
        # check MayaToZBrushClient connection to ZBrushServer
        self.check_connect()

        self.client.check_socket()
        self.check_status_ui()

    def update_network(self):
        """Sends host/port back to client/server instances
        """

        self.client.host = self.user_zbrush_host.getText()
        self.client.port = self.user_zbrush_port.getText()

        self.serv.host = self.user_maya_host.getText()
        self.serv.port = self.user_maya_port.getText()

        self.shared_dir = self.user_shared_dir.getText()

    def check_connect(self, *args):
        """Connects to ZBrushServer using MayaToZBrushClient instance
        """
        self.update_network()
        with maya_tools.utils.err_handler(self.error_gui):
            self.client.connect()
        self.check_status_ui()

    def check_status_ui(self):
        """Updates statuslines, connected/disconnected for zbrush
        """
        # check if client is connected, set gui accordingly
        if self.client.status:
            self.zbrush_status_ui.setBackgroundColor((0.0, 1.0, 0.5))
            self.zbrush_status_ui.setLabel(
                'Status: connected (' +
                self.client.host + ':' +
                str(self.client.port) + ')')
        else:
            self.zbrush_status_ui.setBackgroundColor((1, 0, 0))
            self.zbrush_status_ui.setLabel('Status: not connected')

    def send(self, *args):
        """Send to zbrush using client instance

        Assists in some handling of gozbruhBrushID name mistmatches,
        this is done here to easliy create GUI boxes for create/relink

        Client.get_gozid_mistmatches returns a list of gozbruhBrushID mistmatches
        that need to resolved before sending the object to ZBrushServer

        """

        self.client.check_socket()
        try:
            self.check_status_ui()
        except:
            pass

        maya_tools.send(client=self.client)

    def listen(self, *args):
        """Sends back host/port to MayaServer, starts listening
        """
        if utils.validate_connection(self.serv.host, self.serv.port):
            self.serv.stop()
        self.update_network()
        self.serv.status = False

        with maya_tools.utils.err_handler(self.error_gui):
            self.serv.start()

        # check if server is up, set gui accordingly
        if self.serv.status:
            self.maya_status_ui.setBackgroundColor((0.0, 1.0, 0.5))
            self.maya_status_ui.setLabel(
                'Status: listening (' +
                self.serv.host + ':' +
                str(self.serv.port) + ')')
        else:
            self.maya_status_ui.setBackgroundColor((1, 0, 0))
            self.maya_status_ui.setLabel('Status: not listening')

    def set_env_vars(self):
        """Sets the environment variables in preparation for writing config
        files
        """
        # For each server/host entry, write the appropriate config file
        write_data = {utils.MAYA_ENV: '%s:%s' % (self.serv.host,
                                                 self.serv.port),
                      utils.ZBRUSH_ENV: '%s:%s' % (self.client.host,
                                                   self.client.port),
                      utils.SHARED_DIR_ENV: self.shared_dir}
        for env_var_key in write_data:
            os.environ[env_var_key] = write_data[env_var_key]

    def write_config(self, *args):
        """Takes the new user input and sets up everything necessary for the
        writing process
        """
        # Update data for all of the new field entries
        self.update_network()

        # Set env vars
        self.set_env_vars()

        # Write the CONFIG_PATH dirs/files on the current machine.
        utils.install_goz()

        choice = pm.confirmDialog(title="ZBrush Success",
                                  message='Config Write Complete!',
                                  button=['Ok'])

    def default_config(self, *args):
        """If retaining of settings is not desired, the configuration files
        must be removed.
        """
        default_host, default_port = utils.DEFAULT_NET[utils.ZBRUSH_ENV].split(':')
        self.user_zbrush_host.setText(default_host)
        self.user_zbrush_port.setText(default_port)

        default_host, default_port = utils.DEFAULT_NET[utils.MAYA_ENV].split(':')
        self.user_maya_host.setText(default_host)
        self.user_maya_port.setText(default_port)

        default_shared = ''
        if sys.platform == 'darwin':
            default_shared = utils.SHARED_DIR_DEFAULT_OSX
        elif sys.platform == 'win32':
            default_shared = utils.SHARED_DIR_DEFAULT_WIN
        else:
            default_shared = utils.SHARED_DIR_DEFAULT_LINUX

        self.user_shared_dir.setText(default_shared)

    def build(self):
        """Constructs gui
        """
        if pm.window('goz', exists=True):
            pm.deleteUI('goz', window=True)

        self.gui_window = pm.window('goz', title="gozbruh", rtf=True,
                                    width=1000, height=700)

        pm.setUITemplate('attributeEditorTemplate', pushTemplate=True)

        main_layout = pm.frameLayout(label='gozbruh Options', cll=False)
        pm.setParent(main_layout)
        #======================================================================
        # GENERAL
        #======================================================================
                    #########SHARED
        pm.setParent(main_layout)
        general_framelayout = pm.frameLayout(label='General Options',
                                             cll=False)
        pm.setParent(general_framelayout)

        general_rcl = pm.rowColumnLayout(nc=2)
        pm.setParent(general_rcl)
        pm.text(label='Shared Dir\t')
        self.user_shared_dir = pm.textField(text=utils.get_shared_dir(),
                                            width=200)

        #======================================================================
        # SERVER
        #======================================================================
        pm.setParent(main_layout)
                    #########ZBRUSH
        zbrush_layout = pm.frameLayout(label='ZBrush', cll=False)
        pm.setParent(zbrush_layout)
        zbrush_rcl = pm.rowColumnLayout(nc=2)
        zbrush_host, zbrush_port = utils.get_net_info(utils.ZBRUSH_ENV)
        pm.text(label='ZBrush Host\t')
        self.user_zbrush_host = pm.textField(text=zbrush_host, width=200)
        pm.text(label='ZBrush Port\t')
        self.user_zbrush_port = pm.textField(text=zbrush_port, width=200)

        pm.setParent(zbrush_layout)
        self.send_btn = pm.button(label="Send Selection to ZBrush")
        self.conn_btn = pm.button(label="Check Connection to ZBrush")
        self.zbrush_status_ui = pm.text(label='Status: not connected',
                                        height=30,
                                        enableBackground=True,
                                        backgroundColor=(1.0, 0.0, 0.0))

                    #########MAYA
        pm.setParent(main_layout)
        pm.text(' ')
        maya_layout = pm.frameLayout(label='Maya', cll=False)
        pm.setParent(maya_layout)
        maya_rcl = pm.rowColumnLayout(nc=2)
        maya_host, maya_port = utils.get_net_info(utils.MAYA_ENV)
        pm.text(label='Maya Host\t')
        self.user_maya_host = pm.textField(text=maya_host, width=200)
        pm.text(label='Maya Port\t')
        self.user_maya_port = pm.textField(text=maya_port, width=200)

        pm.setParent(maya_layout)
        self.listen_btn = pm.button(label="Listen for Meshes from ZBrush")
        self.maya_status_ui = pm.text(label='Status: not listening',
                                      height=30,
                                      enableBackground=True,
                                      backgroundColor=(1.0, 0.0, 0.0))

        #======================================================================
        # MORE OPTIONS
        #======================================================================
        pm.setParent(main_layout)
        pm.text(' ')
        more_framelayout = pm.frameLayout(label='Maya-Specific Options',
                                          cll=False)
        pm.setParent(more_framelayout)
        more_rcl = pm.rowColumnLayout(nc=3)
        pm.text(label='Import Visual Smooth', width=200)
        self.smooth_radio_col = pm.radioCollection()
        self.smooth_radio_off = pm.radioButton(
            label='Off',
            onc=lambda x: pm.optionVar(iv=('gozbruh_smooth', 0)))
        self.smooth_radio_on = pm.radioButton(
            label='On',
            onc=lambda x: pm.optionVar(iv=('gozbruh_smooth', 1)))
        import_smooth = 0
        if pm.optionVar(ex='gozbruh_smooth'):
            import_smooth = pm.optionVar(q='gozbruh_smooth')
        pm.radioCollection(
            self.smooth_radio_col, e=True,
            sl=self.smooth_radio_on if import_smooth else self.smooth_radio_off)

        pm.text(label='Import Delete Old Mesh', width=200)
        self.delete_radio_col = pm.radioCollection()
        self.delete_radio_off = pm.radioButton(
            label='Off',
            onc=lambda x: pm.optionVar(iv=('gozbruh_delete', 0)))
        self.delete_radio_on = pm.radioButton(
            label='On',
            onc=lambda x: pm.optionVar(iv=('gozbruh_delete', 1)))
        import_delete = 0
        if pm.optionVar(ex='gozbruh_delete'):
            import_delete = pm.optionVar(q='gozbruh_delete')
        pm.radioCollection(
            self.delete_radio_col, e=True,
            sl=self.delete_radio_on if import_delete else self.delete_radio_off)

        pm.setParent(main_layout)
        self.retain_btn = pm.button(label="Save Settings", height=50)
        pm.text('\t')
        self.remove_btn = pm.button(label="Default Settings")

        self.gui_window.show()

    def buttons(self):
        """Attaches methods to callbacks
        """
        self.send_btn.setCommand(self.send)
        self.conn_btn.setCommand(self.check_connect)
        self.listen_btn.setCommand(self.listen)
        self.retain_btn.setCommand(self.write_config)
        self.remove_btn.setCommand(self.default_config)

    @staticmethod
    def error_gui(message):
        """Simple gui for displaying errors
        """
        pm.confirmDialog(
            title=str('gozbruh Error:'),
            message='\n' + str(message),
            button=['Ok'])

    @staticmethod
    def spacer(num):
        """Creates a spacer
        """
        for _ in range(0, num):
            pm.separator(style='none')
