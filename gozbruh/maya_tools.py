"""
Maya Server and ZBrush client classes

MayaServer is used to start a commandPort,
and listen for objects from ZBrush

Objects are loaded when ZBrushServer calls
client.load funcitons with name/path and tool parent

If the SHARED_DIR_ENV is missing MayaServer/MayaToZBrushClient
will start in a local mode

MayaToZBrushClient is used for sending ascii files to ZBrush
from Maya, it also manges gozbruhBrushIDs, and gozbruhParent attributes
These attributes are used to keep track of name changes in maya

Conflicts in the attributes result in renaming on export
or creating new attributes to fit name changes
"""

import os

import socket
import errno

import json
from collections import defaultdict

import maya.cmds as cmds
import pymel.core as pm

from . import errs
from . import utils

# TODO: make this configurable:
# nodes marked for removal from maya on import from ZBrush
GARBAGE_NODES = ['blinn',
                 'blinnSG',
                 'materialInfo',
                 'ZBrushTexture',
                 'place2dTexture2']

#==============================================================================
# CLASSES
#==============================================================================

class MayaServer(object):
    """Server that uses Maya's built-in commandPort to receive meshes from
    zbrush.

    start/stop(host,port) functions open/close the maya commandPort

    Attributes
    ----------
    status : bool
        current server status (up/down)
    host : str
        current host for serving on from utils.get_net_info
    port : str
        current port for serving on from utils.get_net_info
    cmdport_name : str
        formated command port name (xxx.xxx.xxx.xxx:port)
    file_path : str
        current file loaded from ZBrush (full path)
    file_name : str
        current object loaded from ZBrush (name only no ext)
    """

    def __init__(self):
        """Initialization: gets networking info, creates command port name
        """
        self.host, self.port = utils.get_net_info(utils.MAYA_ENV)

        self.cmdport_name = "%s:%s" % (self.host, self.port)
        self.status = False

    def start(self):
        """Starts a Maya command port for the host, port specified
        """

        # check network info
        utils.validate_host(self.host)
        utils.validate_port(self.port)

        self.cmdport_name = "%s:%s" % (self.host, self.port)
        self.status = cmds.commandPort(self.cmdport_name, query=True)

        # if down, start a new command port
        if self.status is False:
            cmds.commandPort(name=self.cmdport_name, sourceType='python')
            self.status = cmds.commandPort(self.cmdport_name, query=True)
        print 'listening %s' % self.cmdport_name

    def stop(self):
        """Stops the maya command port for the host/port specified
        """
        cmds.commandPort(name=self.cmdport_name,
                         sourceType='python', close=True)
        self.status = cmds.commandPort(self.cmdport_name,
                                       query=True)
        print 'closing %s' % self.cmdport_name


class MayaToZBrushClient(object):
    """Client used for sending meshes to Zbrush.

    Uses of this class:
        Object name management between Zbrush/Maya
        Connections to ZBrushServer
        Cleaning and exporting mayaAscii files

    Attributes
    ----------
    status : bool
        status of the connection to ZBrushServer
    objs : list of str
        list of objects to send to ZBrushServer
    host : str
        current host obtained from utils.get_net_info
    port : str
        current port obtained from utils.get_net_info
    sock : socket.socket
        current open socket connection

    """

    def __init__(self):
        """Gets networking information, initalizes client
        """

        self.host, self.port = utils.get_net_info(utils.ZBRUSH_ENV)
        self.status = False
        self.sock = None
        self.objs = None
        self.goz_id = None
        self.goz_obj = None

    def connect(self):
        """Connect the client to the to ZBrushServer
        """

        try:
            # close old socket, might not exist so skip
            self.sock.close()
        except AttributeError:
            print 'no socket to close...'

        self.status = False

        utils.validate_host(self.host)
        utils.validate_port(self.port)

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # time out incase of a bad host/port that actually exists
        self.sock.settimeout(45)

        try:
            self.sock.connect((self.host, int(self.port)))
        except socket.error as err:
            self.status = False
            if errno.ECONNREFUSED in err:
                raise errs.ZBrushServerError(
                    'Connection Refused: %s:%s' % (self.host, self.port))

        self.status = True

    def check_socket(self):
        """Verify connection to ZBrushServer
        """

        if self.sock is None:
            return

        try:
            self.sock.send('check')
            if self.sock.recv(1024) == 'ok':
                # connected
                print 'connected!'
            else:
                # bad connection, clear socket
                self.status = False
                self.sock.close()
                self.sock = None
                print 'conn reset!'

        except socket.error as err:
            # catches server down errors, resets socket
            self.status = False
            self.sock.close()
            self.sock = None
            if errno.ECONNREFUSED in err:
                print 'conn ref'
                # server probably down
            if errno.EADDRINUSE in err:
                # this is fine
                print 'already connected...'
            if errno.EPIPE in err:
                # server down, or unexpected connection interuption
                print 'broken pipe, trying to reconnect'
        except AttributeError:
            print 'need new sock'

    def format_message(self, command, obj_parents):
        """Construct a json string to pass to the zbrush server."""
        objData = defaultdict(list)

        for obj, parent in obj_parents:
            objData[parent].append(obj)

        return json.dumps({'command': command, 'objData': dict(objData)})

    def send(self, objs):
        """Send a file load command to ZBrush via ZBrushServer.
        """
        # export, send
        if self.status:
            obj_parents = export(objs)
            msg = self.format_message('open', obj_parents)
            self.sock.send(msg)
            # check receipt of objs
            self.load_confirm()
        else:
            raise errs.ZBrushServerError(
                'Please connect to ZBrushServer first')

    def load_confirm(self):
        """Check to make sure that sent objects have been loaded after a send.
        'loaded' will be sent back from ZBrushServer
        """

        if self.sock.recv(1024) == 'loaded':
            print 'ZBrush Loaded:'
            print ('\n'.join(self.objs))
        else:
            self.status = False
            self.sock = None
            print 'ZBrushServer is down!'
            raise errs.ZBrushServerError('ZBrushServer is down!')

#==============================================================================
# FUNCTIONS
#==============================================================================

def get_goz_objs():
    """Grab meshes from selection, filter out extraneous DAG objects and
    freeze transforms on objects.
    """
    objs = cmds.ls(selection=True, type='mesh', dag=True)
    if objs:
        xforms = cmds.listRelatives(objs, parent=True, fullPath=True)
        # freeze transform
        cmds.makeIdentity(xforms, apply=True, t=1, r=1, s=1, n=0)
        cmds.select(xforms)
        objs = cmds.ls(selection=True)
    return objs

#------------------------------------------------------------------------------
# Renaming
#------------------------------------------------------------------------------

def handle_renames(objs):
    import gozbruh.mayagui as mayagui
    # check for any gozbruhBrushIDs, and relink/create
    for obj, goz_id in _get_gozid_mismatches(objs[:]):
        # relinked objs are removed from self.client.objs
        # this prevents relinking 2 previous tool histories
        # it stops relinking after the 1st match/relink
        # so pSphere1 contains both meshes, but pSphere2 still exists
        # this prevents overwriting 2 zbrush tools with the same obj

        # the 'skip' option during in the relink gui keeps the obj to look
        # for an alternative history, for example relink the 2nd obj history
        # if skip fails to relink, it will default to 'create'
        objs = mayagui.rename_prompt(obj, goz_id, objs)
    return objs

def rename_prompt(obj, goz_id, objs):
    """Confirm object rename, trigger create or relink then revise
    objlist
    """
    gui_message = """%s has a old ZBrush ID, of %s, try to relink?

                    NOTE! relinking will
                    remove objects named "%s"
                    selected mesh as the new one!!
                    """ % (obj,
                           goz_id,
                           goz_id)

    choice = pm.confirmDialog(title="ZBrush Name Conflict",
                              message=gui_message,
                              button=['Relink', 'Create', 'Skip'])
    if choice == 'Relink':
        # relink to past gozbruhBrushID
        if obj not in objs:
            return
        new_obj = relink(obj, goz_id)
        objs.remove(obj)
        if new_obj not in objs:
            objs.append(new_obj)

    elif choice == 'Create':
        # new object for zbrush
        create(obj)

def relink(obj, goz_id):
    """Relink object name with existing gozbruhBrushID.
    """
    # manages re linking gozbruhBrush IDs, checks for attribute on shape/xform

    # in the case of a object being duplicated this removes the duplicate
    # to prevent deletion, the 'create' option is prefered
    # is only happens when an object was duplicated and merged (original
    # still exists)
    if cmds.objExists(goz_id):
        cmds.delete(goz_id)

    cmds.rename(obj, goz_id)
    return create(goz_id)

def create(obj):
    """Tell ZBrush to treat `obj` as a new object.

    Under the hood this changes a gozbruhBrush ID to match object name.
    """
    # does not change selection:
    cmds.delete(obj, constructionHistory=True)
    shape = cmds.ls(obj, type='mesh', dag=True)[0]
    xform = cmds.listRelatives(shape, parent=True, fullPath=True)[0]
    goz_check_xform = cmds.attributeQuery(
        'gozbruhBrushID', node=xform, exists=True)
    goz_check_shape = cmds.attributeQuery(
        'gozbruhBrushID', node=shape, exists=True)

    if goz_check_shape:
        cmds.setAttr(shape + '.gozbruhBrushID', obj, type='string')
    if goz_check_xform:
        cmds.setAttr(xform + '.gozbruhBrushID', obj, type='string')
    return xform

def _get_gozid_mismatches(objs):
    """Return objects from `objs` whose gozbruhBrushID does not match their name

    Checks object history for instances of gozbruhBrushID,
    returns a list ofgozbruhBrushID/name conflicts

    gozbruhBrushID is created by ZBrush on export and is used to track
    name changes that can occur in maya

    this function compares object current name against the ID
    and returns a list of conflicts

    this list is handled by the gui to allow for dialog boxes
    """
    goz_list = []

    for obj in objs:
        has_attr = cmds.attributeQuery(
            'gozbruhBrushID', node=obj, exists=True)

        if has_attr:
            # check for 'rename'
            goz_id = cmds.getAttr(obj + '.gozbruhBrushID')
            if obj != goz_id:
                goz_list.append((obj, goz_id))
        else:
            # check for old ID in history
            for old_obj in cmds.listHistory(obj):
                has_attr = cmds.attributeQuery('gozbruhBrushID',
                                               node=old_obj,
                                               exists=True)
                if has_attr:
                    goz_id = cmds.getAttr(old_obj + '.gozbruhBrushID')
                    if obj != goz_id:
                        goz_list.append((obj, goz_id))

    # resulting mismatches to be handled
    return goz_list

#------------------------------------------------------------------------------
# Sending / Exporting
#------------------------------------------------------------------------------

def export(objs):
    """Save files.

    Checks for gozbruhParent attr.

    gozbruhParent is used to import objects in correct order in ZBrush
    gozbruhParent determines the top level tool in ZBrush

    If no instance exists, it is created

    Returns
    -------
    list of (str, str)
        list of object, parent pairs
    """
    parents = []

    for obj in objs:
        # export each file individually
        cmds.select(cl=True)
        cmds.select(obj)
        cmds.delete(ch=True)
        ascii_path = utils.make_maya_filepath(obj)
        cmds.file(ascii_path,
                  force=True,
                  options="v=0",
                  type="mayaAscii",
                  exportSelected=True)
        if cmds.attributeQuery('gozbruhParent', node=obj, exists=True):
            # object existed in zbrush, has 'parent' tool
            parent = cmds.getAttr(obj + '.gozbruhParent')
            # append to the end of parents
            parents.append((obj, parent))
        else:
            cmds.addAttr(obj, longName='gozbruhParent', dataType='string')
            cmds.setAttr(obj + '.gozbruhParent', obj, type='string')
            # prepend to the beginning of parents, we want these objects
            # imported first
            parents = [(obj, obj)] + parents

        # maya is often run as root, this makes sure osx can open/save
        # files not needed if maya is run un-privileged
        os.chmod(ascii_path, 0o777)
    return parents

def send(client=None):
    """Send the current selection in Maya to ZBrush.

    client : `MayaToZBrushClient`
        client running in Maya, which can connect to `ZBrushServer`
    """
    pre_btn_script = utils.get_maya_exec_script()
    # Updates the config files if necessary
    if pre_btn_script:
        # FIXME: use subprocess
        os.system(pre_btn_script + ' False')

    if client is None:
        client = MayaToZBrushClient()

    client.check_socket()

    if client.status is False:
        # try last socket, or fail
        with utils.err_handler(error_gui):
            client.connect()

    # construct list of selection, filter meshes
    objs = get_goz_objs()
    if objs:
        objs = handle_renames(objs)
        with utils.err_handler(error_gui):
            client.send(objs)
    else:
        error_gui('Please select a mesh to send')

#------------------------------------------------------------------------------
# Receiving / Importing
#------------------------------------------------------------------------------

def load(file_path, obj_name, parent_name):
    """Import a file exported from ZBrush.

    This is the command sent over the Maya command port from ZBrush.

    Parameters
    ----------
    file_path : str
        Path to the file that we are importing
    obj_name : str
        Name of the object being imported
    parent_name : str
        Name of the parent for the object being imported
    """
    file_name = utils.split_file_name(file_path)
    _cleanup(file_name)
    cmds.file(file_path, i=True,
              usingNamespaces=False,
              removeDuplicateNetworks=True)

    # Set smoothing options if necessary
    if cmds.optionVar(ex='gozbruh_smooth') and not cmds.optionVar(q='gozbruh_smooth'):
        cmds.displaySmoothness(obj_name, du=0, dv=0, pw=4, ps=1, po=1)

    if not cmds.attributeQuery("gozbruhParent", n=obj_name, ex=True):
        cmds.addAttr(obj_name, longName='gozbruhParent', dataType='string')
    cmds.setAttr(obj_name + '.gozbruhParent', parent_name, type='string')

def _cleanup(name):
    """Removes un-used nodes on import of obj
    """

    # Don't delete the old mesh if gozbruh_delete option var exists and is set to
    #     false, simply rename it
    if cmds.optionVar(ex='gozbruh_delete') and not cmds.optionVar(q='gozbruh_delete'):
        if cmds.objExists(name):
            cmds.rename(name, name + '_old')
    else:
        if cmds.objExists(name):
            cmds.delete(name)

    for node in GARBAGE_NODES:
        node = name + '_' + node
        if cmds.objExists(node):
            cmds.delete(node)

#------------------------------------------------------------------------------
# Helpers
#------------------------------------------------------------------------------

def error_gui(message):
    """Simple gui for displaying errors
    """
    pm.confirmDialog(title=str('gozbruh Error:'),
                     message='\n' + str(message),
                     button=['Ok'])

# This is unused and exists only for custom integration like a shelf button:
def start_maya_server():
    """Start a server within Maya to listen for meshes from ZBrush, bypassing
    `mayagui.Win`.
    """
#     pre_btn_script = utils.get_maya_exec_script()
#
#     if pre_btn_script:
#         import subprocess as sub
#         #answer = sub.Popen([pre_btn_script, 'False'], env={'HOME': os.environ['HOME']}, stderr=sub.PIPE)
#         answer = sub.call([pre_btn_script, 'False'], env={'HOME': os.environ['HOME']})

    host, port = utils.get_net_info(utils.MAYA_ENV)

    print 'Starting listen server for gozbruh on %s:%s' % (host, port)
    maya = MayaServer()
    maya.start()

# I believe this is also an unused utility:
def send_zbrush():
    """(MAYA FUNCTION) Executes the window for goZ Maya, and then hides it from
    the user while proceeding to send the meshes through the UI's
    functionality.
    """
    from pymel.core import deleteUI
    import gozbruh.mayagui as mayagui

    pre_btn_script = utils.get_maya_exec_script()
    # Updates the config files if necessary
    if pre_btn_script:
        os.system(pre_btn_script + ' False')

    # This creates the window that will forge the connection to the zBrush
    #     machine.
    win = mayagui.Win()
    # Delete the window
    deleteUI(win.gui_window, wnd=True)
    # Send the geo
    win.send()
