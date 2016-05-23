#! /usr/bin/env python
"""
Starts ZBrushSever, manages ZBrushToMayaClient

ZbrushServer recived strings such as:
    open|objectname#objectparent:anotherobject#anotherparent...

These are parsed and opened in ZBrush with the use of some apple script

ZBrushToMayaClient conencts to a open commandPort in maya

gozbruh.maya_tools.load(file,objname,objparent) is used to open files
"""
import sys
import os

import socket
import SocketServer
from threading import Thread

import json

# FIXME: this should not be necessary
CURRDIR = os.path.dirname(os.path.dirname(os.path.abspath(sys.modules[__name__].__file__)))
sys.path.append(CURRDIR)
from . import utils

#==============================================================================
# CLASSES
#==============================================================================

class ZBrushServer(object):
    """ZBrush server that gets meshes from Maya.

    Simplifies use of `ZBrushSocketServ`.

    Attributes
    ----------
    status : bool
        current server status (up/down)
    host : str
        current host for serving on from utils.get_net_info
    port : str
        current port for serving on from utils.get_net_info
    cmdport_name : str
        formated command port name
    """
    def __init__(self, host, port):
        """Initializes server with host/port to server on, send from
        gozbruh.zbrushgui
        """

        self.host = host
        self.port = port
        self.server = None
        self.server_thread = None
        self.status = False

    def start(self):
        """Looks for previous server, trys to start a new one
        """

        self.status = False

        utils.validate_host(self.host)
        utils.validate_port(self.port)

        if self.server is not None:
            print 'killing previous server...'
            self.server.shutdown()
            self.server.server_close()

        print 'starting a new server!'

        self.server = ZBrushSocketServ(
            (self.host, int(self.port)), ZBrushHandler)
        self.server.allow_reuse_address = True
        self.server_thread = Thread(target=self.server.serve_forever)
        self.server_thread.daemon = True
        self.server_thread.start()
        print 'Serving on %s:%s' % (self.host, self.port)
        self.status = True

    def stop(self):
        """Shuts down ZBrushSever
        """
        self.server.shutdown()
        self.server.server_close()
        print 'stoping...'
        self.status = False


class ZBrushSocketServ(SocketServer.ThreadingMixIn, SocketServer.TCPServer):
    """Extends socket server with custom settings and configures daemon mode
    for socketserv module.
    """
    timeout = 5
    daemon_threads = True
    allow_reuse_address = True

    # handler is the RequestHandlerClass
    def __init__(self, server_address, handler):
        SocketServer.TCPServer.__init__(
            self,
            server_address,
            handler)

    def handle_timeout(self):
        print 'TIMEOUT'


class ZBrushHandler(SocketServer.BaseRequestHandler):
    """Custom handler for ZBrushSever and handles loading objects from maya

    splits the open command:
    open|objectname#objectparent:anotherobject#anotherparent...

    Also response with 'loaded' on sucessful object load

    If 'check' is send from MayaToZBrushClient a 'ok' send back
    this is used to check if the server is up/ready

    Can be sent 'EXIT' to stop the server thread completely

    """

    def handle(self):
        # keep handle open until client/server close
        while True:
            data = self.request.recv(1024).strip()
            if not data:
                self.request.close()
                break

            # check for conn-reset/disconnect by peer (on client)
            if data == 'check':
                self.request.send('ok')

            # Shutdown sequence
            if data == 'EXIT':
                self.server.server_close()

            # if we get to here then data must be our json string
            data = json.loads(data)

            # parse object list from maya
            if data.get('command') == 'open':
                objData = data.get('objData')
                for parent, objs in objData.iteritems():
                    for obj in objs:
                        print 'got: ' + obj
                        zs_temp = self.get_loader_zscript(obj + '.ma', parent)
                        utils.send_osa(zs_temp)
                print 'loaded all objs!'
                self.request.send('loaded')

    @staticmethod
    def get_loader_zscript(name, parent):
        """Writes a temporary zscript to perform the loading of file `name`.

        The script is saved in CONFIG_PATH/.zbrush/gozbruh/temp/zbrush_load.txt
        """
        script_path = os.path.join(utils.CONFIG_PATH, 'temp')
        if not os.path.exists(script_path):
            os.makedirs(script_path)
        script_path = os.path.join(script_path, 'zbrush_load.txt')
        zs_temp = open(script_path, 'w+')

        env = utils.get_shared_dir()
        print env

        # zbrush script to iterate through sub tools,
        # and open matches, appends new tools

        zscript = """

                //this is a new set of import functions
                //it allows the loop up of top level tools
                //routine to locate a tool by name
                //ZBrush uses ToolID, SubToolID, and UniqueID's
                //All of these are realative per project/session

                //find subtool

                [RoutineDef, findSubTool,


                    //iterate through sub tools
                    //even though the ui element exists
                    //it may not be visable
                    [SubToolSelect,0]

                    [Loop,[SubToolGetCount],

                        //get currently selected tool name to compare
                        [VarSet,currentTool,[IgetTitle, Tool:Current Tool]]
                        [VarSet,subTool, [FileNameExtract, #currentTool, 2]]
                        [If,([StrLength,"#TOOLNAME"]==[StrLength,#subTool])&&([StrFind,#subTool,"#TOOLNAME"]>-1),
                            //there was a match, import
                            //stop looking
                            [LoopExit]
                        ,]
                        //move through each sub tool to make it visable
                        [If,[IsEnabled,Tool:SubTool:SelectDown],
                            [IPress, Tool:SubTool:SelectDown]

                            ,
                            [IPress, Tool:SubTool:Duplicate]
                            [IPress, Tool:SubTool:MoveDown]
                            [IPress, Tool:SubTool:All Low]
                            [IPress, Tool:Geometry:Del Higher]
                            [LoopExit]
                        ]
                    ]

                ]


                //find parent

                [RoutineDef, findTool,

                    //ToolIDs befor 47 are 'default' tools
                    //48+ are user loaded tools
                    //this starts the counter at 48
                    //also gets the last 'tool'
                    [VarSet,count,[ToolGetCount]-47]
                    [VarSet,a, 47]

                    //flag for if a object was found
                    //or a new blank object needs to be made
                    [VarSet, makeTool,0]

                    //shuts off interface update
                    [IFreeze,

                    [Loop, #count,
                        //increment current tool
                        [VarSet, a, a+1]

                        //select tool to look for matches
                        [ToolSelect, #a]
                        [SubToolSelect,0]

                        //check for matching tool
                        //looks in the interface/UI
                        [VarSet, uiResult, [IExists,Tool:SubTool:#PARENT]]

                        [If, #uiResult == 1,
                            //check to see if tool is a parent tool
                            //if it is select it, otherwise iterate to find sub tool
                            //ideally direct selection of the subtool would be posible
                            //but sub tools can potentially be hidden in the UI
                            //findSubTool iterates through sub tools to find a match
                            [If, [IExists,Tool:#PARENT],
                            [IPress, Tool:#PARENT],
                            ]

                            [RoutineCall, findSubTool]
                            [VarSet, makeTool,0]
                            [LoopExit]
                        ,
                            [VarSet,makeTool,1]

                        ]
                    ]
                    //check to see if found or needs a new blank mesh
                    [If, #makeTool==1,
                    //make a blank PolyMesh3D
                    [ToolSelect, 41]
                    [IPress,Tool:Make PolyMesh3D]

                    ,
                    //otherwise
                    //find sub tool

                    ]
                    ]
                ]


                //find 'parent tool
                //check for sub tool
                //if found import
                //if missing make new tool

                [RoutineDef, open_file,
                    //check if in edit mode
                    [VarSet, ui,[IExists,Tool:SubTool:All Low]]

                    //if no open tool make a new tool
                    // this could happen if there is no active mesh
                    [If, ui == 0,
                    [ToolSelect, 41]
                    [IPress,Tool:Make PolyMesh3D]
                    ,
                    ]

                    //find parent
                    [RoutineCall, findTool]

                    //lowest sub-d
                    [IPress, Tool:SubTool:All Low]
                    [FileNameSetNext,"!:#FILENAME"]
                    //finally import the tool
                    [IPress,Tool:Import]
                ]

                [RoutineCall,open_file]

                """

        # swap above zscript #'s with info from maya
        # then write to temp file
        zscript = zscript.replace('#FILENAME', os.path.join(env, name))
        zscript = zscript.replace('#TOOLNAME', name.replace('.ma', ''))
        zscript = zscript.replace('#PARENT', parent)
        zs_temp.write(zscript)
        zs_temp.flush()
        zs_temp.close()
        return zs_temp.name


class ZBrushToMayaClient(object):
    """Client that connects to Maya's command port and sends commands to load
    exported ZBrush meshes.

    Attributes
    ----------
    self.host : str
        current host obtained from utils.get_net_info
    self.port : str
        current port obtained from utils.get_net_info

    Also contains a method to check operation with maya ZBrushToMayaClient.test_client()

    ZBrushToMayaClient.send() is used by the GUI installed in ZBrush by running:
    python -m gozbruh.zbrush_tools

    this executes this module as a script with command line arguments
    the args contain objectname, and object parent tool

    gozbruh.utils.osa_send is used to create a gui in ZBrush

    gozbruh.utils.osa_open is also used to open ZBrush

    """

    def __init__(self, host, port):
        """ inits client with values from gui"""
        self.host = host
        self.port = port

    def test_client(self):
        """ tests connection with maya, creates a sphere and deletes it """

        utils.validate_host(self.host)
        utils.validate_port(self.port)

        maya_cmd = 'import maya.cmds as cmds;'
        maya_cmd += 'cmds.sphere(name="goz_server_test;")'
        maya_cmd += 'cmds.delete("goz_server_test")'
        maya = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        maya.settimeout(5)
        try:
            maya.connect((self.host, int(self.port)))
        except socket.error as err:
            print err
            print 'connection refused'
            return False
        except ValueError:
            print 'specify a valid port'
            return False
        else:
            maya.send(maya_cmd)
            maya.close()
            return True

    @staticmethod
    def send(obj_name, parent_name):
        """Sends a file to maya

        includes filepath, object name, and the "parent"

        The parent is the top level tool or sub tool 0 of the current tool
        this is used to preserve organization when loading back into ZBrush

        connects to maya commandPort and sends the maya commands

        """

        print 'Parent tool: ' + parent_name

        # construct file read path for maya, uses SHARED_DIR_ENV
        # make realative path
        file_path = utils.make_maya_filepath(obj_name)

        print file_path

        maya_cmd = 'import gozbruh.maya_tools as maya_tools;maya_tools.load(\'' + \
            file_path + '\',\'' + obj_name + \
            '\',\'' + \
            parent_name + \
            '\')'

        print maya_cmd

        maya_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        host, port = utils.get_net_info(utils.MAYA_ENV)

        print host, port

        try:
            maya_sock.connect((host, int(port)))
        except socket.error as err:
            print err
            print 'connection refused'
        except ValueError:
            print 'specify a valid port'
        else:
            maya_sock.send(maya_cmd)
            maya_sock.close()

#==============================================================================
# FUNCTIONS
#==============================================================================

def start_zbrush_server():
    """Start the server and execute the UI installation for ZBrush.

    Assumes ZBrush is running.
    """
    import time

    # Guarentee that the pre-button script has run once before server starts

#     pre_btn_script = utils.get_zbrush_exec_script()
#     if pre_btn_script:
#         os.system(pre_btn_script + " False")

    host, port = utils.get_net_info(utils.ZBRUSH_ENV)
    print host, port

    # Make sure that all previous servers have been shutdown before attempting
    #     to start a new one!
    if utils.validate_connection(host, port):
        utils.force_zbrush_server_close()
        # Make sure that the server is actually closed before starting the new one
        while utils.validate_connection(host, port):
            time.sleep(.1)

    # Start the server

    server = ZBrushServer(host, port)
    server.start()

    # Now that the server has been started, run the UI script
    activate_zscript_ui()

    # Listen loop for the server thread

    while server.server_thread.isAlive():
        time.sleep(1)

def activate_zbrush():
    """Apple script to open ZBrush and bring to front
    """
    utils.open_osa()

def activate_zscript_ui():
    """Assembles a zscript to be loaded by ZBrush to create GUI buttons.
    The config variables are read in and then used.
    """

    # zscript to create the 'send' button
    zscript = """
    [RoutineDef, send_file,

        //GET CURRENT ENV VARIABLES FROM THE CONFIG FILE


        //First execute the script to set/write variables
        [VarSet, execScript, "#PRE_EXEC_SCRIPT"]
        [VarSet, exists, [FileExists, [StrMerge, "!:", #execScript]]]
        [If, exists == 1,
            [ShellExecute, #execScript]
        ]

        //check if in edit mode
        [VarSet, ui,[IExists,Tool:SubTool:All Low]]

        //if no open tool make a new tool
        [If, ui == 0,
        [ToolSelect, 41]
        [IPress,Tool:Make PolyMesh3D]
        ,]

        //set lowest subtool resolution
        [IPress, Tool:SubTool:All Low]

        //env_path set to the path to the config for shared_dir
        [VarSet, env_path, "!:#ENVPATH"]
        [MemCreateFromFile, envVarBlock, #env_path]
        [MemReadString, envVarBlock, env_path]
        [VarSet, env_path, [StrMerge, "!:", env_path, "/"]]

        //extracts the current active tool name
        [VarSet, tool_name,[FileNameExtract, [GetActiveToolPath], 2]]

        //appends .ma to the path for export, construct filename
        [VarSet, file_name, [StrMerge,tool_name,".ma"]]

        //python module execution command, needs to be abs path
        [VarSet, module_path, "/usr/bin/python #GOZ_COMMAND_SCRIPT send "]

        [VarSet, validpath,[FileExists, #env_path]]

        [If, validpath != 1,


            //prevents zbrush crash from exporting to a invalid path
            //if zbrush exports to a bad path it will lock up
            [MessageOK, "Invalid ZDOCS file path for export"]
            [MessageOK, #env_path]
            [Exit]
            ,


        ]

        //append env to file path
        [VarSet, export_path, [StrMerge,env_path,file_name] ]

        //set the maya 'template?' I think ofer spelled something wrong
        //this sets the file name for the next export \w correct 'template'
        [FileNameSetNext, #export_path,"ZSTARTUP_ExportTamplates\Maya.ma"]

        //finally export the tool
        [IPress,Tool:Export]

        //get base tool
        [SubToolSelect,0]

        [VarSet,base_tool,[IgetTitle, Tool:Current Tool]]
        [VarSet,base_tool, [FileNameExtract, #base_tool, 2]]

        //trigger the python module to send maya the load commands

        [ShellExecute,
            //merge the python command with the tool name
            [StrMerge, #module_path,
                    #tool_name, " ",#base_tool
            ]
        ]
    ]

    //gui button for triggering this script
    [IButton, "TOOL:Send to Maya", "Export model as a *.ma to maya",
        [RoutineCall, send_file]
    ]

    """

    # zscript to create the 'send -all' button
    zscript += """
    [RoutineDef, send_all,

        //First execute the script to set/write variables
        [VarSet, execScript, "#PRE_EXEC_SCRIPT"]
        [VarSet, exists, [FileExists, [StrMerge, "!:", #execScript]]]
        [If, exists == 1,
            [ShellExecute, #execScript]
        ]

        //check if in edit mode
        [VarSet, ui,[IExists,Tool:SubTool:All Low]]

        //if no open tool make a new tool
        [If, ui == 0,
        [ToolSelect, 41]
        [IPress,Tool:Make PolyMesh3D]
        ,]

        //set all tools to lowest sub-d
        [IPress, Tool:SubTool:All Low]

        //iterator variable
        [VarSet,t,0]

        //start at the first subtool
        [SubToolSelect,0]

        //iterate through all subtools
        [Loop,[SubToolGetCount],

            //increment iterator
            [VarSet,t,t+1]

            //select current subtool index in loop
            [SubToolSelect,t-1]

            //set base export path #ENVPATH is replace with SHARED_DIR_ENV (expanded)
            [VarSet, env_path, "!:#ENVPATH"]
            [MemCreateFromFile, envVarBlock, #env_path]
            [MemReadString, envVarBlock, env_path]
            [VarSet, env_path, [StrMerge, "!:", env_path, "/"]]

            //current tool name
            [VarSet, tool_name, [FileNameExtract, [GetActiveToolPath], 2]]

            //start constructing export file path /some/dir/tool.ma
            [VarSet, file_name, [StrMerge,tool_name,".ma"]]

            //base python module shell command, needs to be abs path
            [VarSet, module_path, "/usr/bin/python #GOZ_COMMAND_SCRIPT send "]

            [VarSet, validpath,[FileExists, #env_path]]

            [If, validpath != 1,


                //prevents zbrush crash from exporting to a invalid path
                //if zbrush exports to a bad path it will lock up
                [MessageOK, "Invalid ZDOCS file path for export"]
                [MessageOK, #env_path]
                [Exit]
                ,


            ]

            //full export path
            [VarSet, export_path, [StrMerge,env_path,file_name] ]

            //set export path to be used by next command
            [FileNameSetNext, #export_path,"ZSTARTUP_ExportTamplates\Maya.ma"]

            //finally export
            [IPress,Tool:Export]


            //get base tool
            [SubToolSelect,0]
            [VarSet,base_tool,[IgetTitle, Tool:Current Tool]]
            [VarSet,base_tool, [FileNameExtract, #base_tool, 2]]

            [ShellExecute,
                //join module_path tool_name for maya to load
                [StrMerge, #module_path, #tool_name, " ",#base_tool]
            ]
        ]
    ]
    [IButton, "TOOL:Send to Maya -all", "Export model as a *.ma to maya",
        [RoutineCall, send_all]
    ]
    """

    # zscript to create the 'send -vis' button
    zscript += """
    [RoutineDef, send_visable,

        //First execute the script to set/write variables
        [VarSet, execScript, "#PRE_EXEC_SCRIPT"]
        [VarSet, exists, [FileExists, [StrMerge, "!:", #execScript]]]
        [If, exists == 1,
            [ShellExecute, #execScript]
        ]

        //check if in edit mode
        [VarSet, ui,[IExists,Tool:SubTool:All Low]]

        //if no open tool make a new tool
        [If, ui == 0,
        [ToolSelect, 41]
        [IPress,Tool:Make PolyMesh3D]
        ,]

        //set all tools to lowest sub-d
        [IPress, Tool:SubTool:All Low]

        //iterator variable
        [VarSet,t,0]

        //start at the first subtool
        [SubToolSelect,0]

        //iterate through all subtools
        [Loop,[SubToolGetCount],

            //increment iterator
            [VarSet,t,t+1]

            //select current subtool index in loop
            [SubToolSelect,t-1]

            //set base export path #ENVPATH is replace with SHARED_DIR_ENV (expanded)
            [VarSet, env_path, "!:#ENVPATH"]
            [MemCreateFromFile, envVarBlock, #env_path]
            [MemReadString, envVarBlock, env_path]
            [VarSet, env_path, [StrMerge, "!:", env_path, "/"]]

            //current tool name
            [VarSet, tool_name, [FileNameExtract, [GetActiveToolPath], 2]]

            //start constructing export file path /some/dir/tool.ma
            [VarSet, file_name, [StrMerge,tool_name,".ma"]]

            //base python module shell command, needs to be absolute path
            [VarSet, module_path, "/usr/bin/python #GOZ_COMMAND_SCRIPT send "]

            [VarSet, validpath,[FileExists, #env_path]]

            [If, validpath != 1,


                //prevents zbrush crash from exporting to a invalid path
                //if zbrush exports to a bad path it will lock up
                [MessageOK, "Invalid ZDOCS file path for export"]
                [MessageOK, #env_path]
                [Exit]
                ,


            ]

            //full export path
            [VarSet, export_path, [StrMerge,env_path,file_name] ]

            //set export path to be used by next command
            [FileNameSetNext, #export_path,"ZSTARTUP_ExportTamplates\Maya.ma"]

            //check visablility
            [VarSet,curTool,[IgetTitle, Tool:Current Tool]]
            //look at interface mod
            [If,[IModGet,[StrMerge,"Tool:SubTool:",curTool]] >= 16,
                //finally export if visable
                [IPress,Tool:Export]

                //get base tool
                [SubToolSelect,0]
                [VarSet,base_tool,[IgetTitle, Tool:Current Tool]]
                [VarSet,base_tool, [FileNameExtract, #base_tool, 2]]

                [ShellExecute,
                    //join module_path tool_name for maya to load
                    [StrMerge, #module_path, #tool_name, " ",#base_tool]
                ]

                ,
            ]
        ]
    ]
    [IButton, "TOOL:Send to Maya -visible", "Export model as a *.ma to maya",
        [RoutineCall, send_visable]
    ]
    """

    # Get the path to the file that needs to be exec before button calls if
    #     it exists.
    script_to_exec = utils.get_zbrush_exec_script()
    command_script = utils.get_goz_command_script()

    # Create the temp directory if it does not already exist in the config path
    script_path = os.path.join(utils.CONFIG_PATH, 'temp')
    if not os.path.exists(script_path):
        os.makedirs(script_path)
    script_path = os.path.join(script_path, 'zbrush_gui.txt')

    env = utils.get_shared_dir_config()

    zscript = zscript.replace('#ENVPATH', env)
    zscript = zscript.replace('#GOZ_COMMAND_SCRIPT', command_script)
    zscript = zscript.replace('#PRE_EXEC_SCRIPT', script_to_exec)

    try:
        zs_temp = open(script_path, 'w+')
        zs_temp.write(zscript)
        zs_temp.flush()
    finally:
        zs_temp.close()

    utils.send_osa(script_path)
