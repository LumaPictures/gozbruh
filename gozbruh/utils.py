#! /usr/bin/env python

"""
Utilities for all gozbruh functionality

Constants
---------
CURRDIR : str
    Current file path directory
SHARED_DIR_ENV : str
    String representing the shared_dir in other places
SHARED_DIR_DEFAULT_* : str
    String representing the sahred_dir defaults for different platforms

MAYA_ENV : str
    String representing the Maya environment
ZBRUSH_ENV : str
    String representing the ZBrush environment
GOZ_HELP : str
    String representing the gozbruh help
GOZ_LOG_PATH_FILE
    String representing the location of the gozbruh Log if it is needed
DEFAULT_NET : dict
    Dict containing the default values to the MAYA/ZBRUSH env keys above
ENV_TO_CONFIG_FILE : dict
    Dict containing the names for the config files pertaining to the
    configurable keys above
"""

import sys
import os
import socket
import time
from contextlib import contextmanager

from . import errs

# FIXME: will this affect all of python or just this file?
sys.dont_write_bytecode = True

# Default Paths
# -------------

CONFIG_PATH = os.path.abspath(os.path.join(os.environ['HOME'], '.zbrush', 'gozbruh'))

# currently only OSX is supported due to apple script usage
SHARED_DIR_DEFAULT_OSX = '/Users/Shared/Pixologic/gozbruhProjects'
# win32 api could be used on windows
SHARED_DIR_DEFAULT_WIN = 'C:\\Users\\Public\\Pixologic\\gozbruhProjects'

SHARED_DIR_DEFAULT_LINUX = os.path.join(CONFIG_PATH, 'temp')

GOZ_LOG_PATH_FILE = os.path.join(os.environ['HOME'], '.gozbruhLog')

# Environment Variables
# ----------------------

SHARED_DIR_ENV = 'SHARED_ZDOCS'

# maya network info env
MAYA_ENV = 'MAYA_HOST'
# zbrush network info env
ZBRUSH_ENV = 'ZBRUSH_HOST'
# default network info
DEFAULT_NET = {MAYA_ENV: ':6667', ZBRUSH_ENV: ':6668'}

# Configuration Files
# -------------------
# we use multiple files instead of a single configuration file (json, ini, etc)
# because we may need to read these from ZBrush, which is very crippled in
# terms of scripting.
ENV_TO_CONFIG_FILE = {
    MAYA_ENV: 'MayaHost',
    ZBRUSH_ENV: 'ZBrushHost',
    SHARED_DIR_ENV: 'ShareDir'
}
GOZ_HELP = '.gozbruhConfigHelp'
ZBRUSH_PRE_EXEC = 'ZBrushPreExec'
MAYA_PRE_EXEC = 'MayaPreExec'

@contextmanager
def err_handler(gui):
    """Handles general gozbruh errors, raises a gui/logger on err
    """

    try:
        yield
    except (errs.PortError,
            errs.IpError,
            errs.SelectionError,
            errs.ZBrushServerError) as err:
        print err.msg
        gui(err.msg)
    except Exception as err:
        print err
        gui(err)
    finally:
        pass

def validate_port(port):
    """Checks port is valid,or raises an error
    """

    try:
        port = int(port)
    except ValueError:
        raise errs.PortError(port, 'Please specify a valid port: %s' % (port))

def validate_host(host):
    """Validates IP/host, or raises and error
    """

    try:
        host = socket.gethostbyname(host)
    except socket.error:
        raise errs.IpError(host, 'Please specify a valid host: %s' % (host))

def validate_connection(host, port):
    """Checks to see if a connection exists at the current hos and port

    Parameters
    ----------
    host : str
        host string
    port : str
        port string

    Returns
    -------
    boolean
        True for valid connection, False if not
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
        s.connect((host, int(port)))
        s.close()
    except:
        return False
    return True

def validate(net_string):
    """Runs host/port validation on a string
    """

    host, port = net_string.split(':')
    validate_host(host)
    validate_port(port)
    return (host, port)

def get_config_file(var):
    """Gets the absolute path for a config file associated with a particular
    environment variable
    """
    return os.path.join(CONFIG_PATH, ENV_TO_CONFIG_FILE[var])

def get_zbrush_exec_script():
    """Returns the path to the ZBrush Pre-Exec script if it exists, '' if not.
    """
    return os.path.join(CONFIG_PATH, ZBRUSH_PRE_EXEC)

def get_goz_command_script():
    this_file = os.path.abspath(sys.modules[__name__].__file__)
    return os.path.join(os.path.dirname(this_file), 'cmd.py')

def get_maya_exec_script():
    """Returns the path to the Maya Pre-Exec script if it exists, '' if not.
    """
    cfg = os.path.join(CONFIG_PATH, MAYA_PRE_EXEC)
    if os.path.exists(cfg):
        return cfg
    else:
        return ''

def get_shared_dir_config():
    """Returns the path to the config file for the shared_dir
    """
    return get_config_file(SHARED_DIR_ENV)

def get_shared_dir():
    """Returns the string representation of the shared directory.

    First it checks for env variables and if not found, checks the config files

    Returns
    -------
    shared_dir : str
    """
    # Check for env variable for shared dir
    shared_dir = os.getenv(SHARED_DIR_ENV)
    if not shared_dir:
        # If there's no shared dir, check for the config file
        cfg = get_config_file(SHARED_DIR_ENV)
        if os.path.exists(cfg):
            shared_dir = config_read(SHARED_DIR_ENV)

    # If the shared_dir still doesn't exist, lets use the defaults
    if not shared_dir:
        if sys.platform == 'darwin':
            shared_dir = SHARED_DIR_DEFAULT_OSX
        else:
            shared_dir = SHARED_DIR_DEFAULT_LINUX

    return shared_dir

def get_net_info(net_env):
    """Gets the net information (host, port) for a given net environment.

    First checks environment variables, then config files, and if
    those are empty, it uses the DEFAULT_NET values.
    **Missing SHARED_DIR_ENV forces local mode

    Parameters
    ----------
    net_env : str

    Returns
    -------
    host, port : str
    """

    # check the shared dir first. it could force us into local mode
    shared_dir = get_shared_dir()

    # check for empty but existing env var
    if shared_dir is '':
        shared_dir = None

    if shared_dir is None:
        # if no shared directory is set, start in local modee
        print "No shared directory set. Defaulting to local mode"
        if sys.platform == 'darwin':
            print "working on OSX"
            os.environ[SHARED_DIR_ENV] = SHARED_DIR_DEFAULT_OSX
        elif sys.platform == 'win32' or sys.platform == 'win64':
            print "working on Windows"
            os.environ[SHARED_DIR_ENV] = SHARED_DIR_DEFAULT_WIN
    else:
        net_string = os.environ.get(net_env, '')

        if not net_string:
            # Check for a config getter
            cfg = get_config_file(net_env)
            if os.path.exists(cfg):
                net_string = config_read(net_env)

        if net_string:
            host, port = validate(net_string)
            return host, port

    # finally default to local mode
    net_string = DEFAULT_NET[net_env]

    if net_string:
        host, port = validate(net_string)
        return host, port

def split_file_name(file_path):
    """Gets the file 'name' from file, strips ext and dir
    """
    file_name = os.path.splitext(file_path)[0]
    file_name = os.path.split(file_name)[1]

    return file_name

def make_maya_filepath(name):
    """Makes a full resolved file path for zbrush
    """
    return os.path.join(get_shared_dir(), name) + '.ma'

def send_osa(script_path):
    """Sends a zscript file for zbrush to open
    """
    cmd = ['osascript -e',
           '\'tell app "ZBrush"',
           'to open',
           '"' + script_path + '"\'']

    cmd = ' '.join(cmd)
    print cmd
    os.system(cmd)

def config_write(var, text):
    """Writes the configuration file for the variable specified.
    *The variables that can have configuration files are declared in the
    utils.ENV_TO_CONFIG_FILE
    """
    cfg = get_config_file(var)
    if not os.path.exists(os.path.dirname(cfg)):
        os.makedirs(os.path.dirname(cfg))
    try:
        cfg_write = open(cfg, 'w')
        cfg_write.write(text)
    finally:
        cfg_write.close()

def config_read(var):
    """Reads the configuration file for the variable specified.
    *The variables that can have configuration files are declared in the
    utils.ENV_TO_CONFIG_FILE
    """
    cfg = get_config_file(var)
    info = ''
    if os.path.exists(cfg):
        try:
            config = open(cfg, 'r')
            info = config.read()
        finally:
            config.close()
    else:
        print 'No configuration files have been created yet for %s.' % var
    return info

def open_osa():
    """Opens ZBrush

    blocks untill ZBrush is ready for addional commands
    makes sure ZBrush is ready to install the GUI

    launches ZBrush
    loop to check if ZBrush is 'ready'
    brings ZBrush to front/focus
    clears any crash messages

    """

    osa = "osascript "\
        + "-e 'tell application \"ZBrush\" to launch' "\
        + "-e 'tell application \"System Events\"' "\
        + "-e 'repeat until visible of process \"ZBrushOSX\" is false' "\
        + "-e 'set visible of process \"ZBrushOSX\" to false' "\
        + "-e 'end repeat' "\
        + "-e 'end tell' "\
        + "-e 'tell application \"System Events\"' "\
        + "-e 'tell application process \"ZBrushOSX\"' "\
        + "-e 'set frontmost to true' "\
        + "-e 'keystroke return' "\
        + "-e 'end tell' "\
        + "-e 'end tell'"

    print osa
    os.system(osa)

def force_zbrush_server_close(host=None, port=None):
    """Forces the ZBrush server to close under the current configuration
    specified in either the environment variables or the config files. If no
    parameters are passed in, the one's setup in the configs will be used.
    If there are none there, then the defaults will be used.

    Parameters
    ----------
    host : str
        (optional) host string
    port : str
        (optional) port string
    """

    if host is None or port is None:
        host, port = get_net_info(ZBRUSH_ENV)
        print host, port

    if validate_connection(host, port):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1)
            s.connect((host, int(port)))
            s.send('EXIT')
            time.sleep(1)
            s.close()
        except:
            print 'The server has been closed!'

def create_config_path():
    """Creates the configuration file path for the current machine.  This needs
    to be done for each machine using gozbruh regardless of platform.

    (If environment variables are set for the configuration options, they will
    be written for each of the config files needed)
    """
    if not os.path.exists(CONFIG_PATH):
        print 'Creating gozbruh Configuration Path...'
        # Create the config path directory
        os.makedirs(CONFIG_PATH)

    # Create blank config files for each of the attributes unless env vars
    #     are present for the variable, in which case write those.
    for key in ENV_TO_CONFIG_FILE:
        try:
            cfg_write = open(get_config_file(key), 'w')
            write_val = os.environ.get(key, '')
            cfg_write.write(write_val)
        finally:
            cfg_write.close()

def get_zbrush_app_dirs():
    """Returns a list of the ZBrush install locations for OSX
    """
    app_dirs = os.listdir('/Applications')
    return [d for d in app_dirs if 'ZBrush' in d]

def install_goz_osx(app_dirs=None):
    """Installs the startup scripts for gozbruh installation.  Uses the list of dirs
    if there's one passed in, otherwise tries to find all of the system's
    installations of ZBrush

    Parameters
    ----------
    install_dir_list : list of str
        (optional) List of all of the ZBrush directories to install to
    """
    # Get the ZBrush Application directory
    if app_dirs is None:
        app_dirs = get_zbrush_app_dirs()
        if not app_dirs:
            raise Exception('ZBrush not installed in /Applications')

    this_file = os.path.abspath(sys.modules[__name__].__file__)

    for app_dir in app_dirs:
        print 'Installing gozbruh for ZBrush in directory %s' % app_dir
        default_script = os.path.join(os.path.dirname(this_file), 'DefaultZScript.txt')
        script_path = os.path.join('/Applications', app_dir, 'ZScripts')
        script_orig = os.path.join(script_path, 'DefaultZScript.zsc')
        script_new = os.path.join(script_path, 'DefaultZScript.txt')

        if not os.path.exists(script_new):
            # If it does exist, we are going to be creating the new DefaultZScript
            # Installation of the new DefaultZScript.  Takes place outside
            #     of Zbrush.

            try:
                default_script_read = open(default_script, 'r')
                default_script_str = default_script_read.read()
            finally:
                default_script_read.close()
            print 'Installing gozbruh Startup Files for ZBrush...'

            # Write the new DefaultZScript.txt
            command_script = get_goz_command_script()
            new_script_str = default_script_str.replace('#GOZ_COMMAND_SCRIPT',
                                                        command_script)

            try:
                script_new_write = open(script_new, 'w')
                script_new_write.write(new_script_str)
                print 'Wrote ZBrush Startup Script:  %s' % script_new
            finally:
                script_new_write.close()

def install_goz(app_dir_list=None):
    """Essentially an 'install' script for gozbruh.  Takes care of setting up the
    essentials of what gozbruh needs to run.
    """
    if sys.platform == 'darwin':
        install_goz_osx(app_dir_list)

    create_config_path()

    print '----------  gozbruh Installation Finished!  ----------\n'\
          '\n(Config folder can be found in your home directory %s)' % CONFIG_PATH
