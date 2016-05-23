# go-zbruh Command Port

Sync meshes between Maya and ZBrush running on different workstations.

Limitations:
- If using two machines, they must have a shared network drive
- ZBrush is currently only supported on OSX.  We welcome a pull request from 
  someone from the Windows world.


## Installation

### ZBrush

1. Install the python module on the ZBrush workstation:

    ```
    git clone https://github.com/LumaPictures/gozbruh
    cd gozbruh
    python setup.py install
    ```

2. Run the configuration script UI (If your system is setup properly,
   the previous step should have installed the script on your executable path,
   otherwise, the script will be in your python bin/scripts directory):

    ```
    goz_config
    ```

   Set up your configuration options and write the config files.  
   For ZBrush machines, you may be presented with an option to choose which 
   currently installed versions of ZBrush that you would like to install the 
   files for.

### Maya

1. Install the python module on the Maya workstation:

    ```
    git clone https://github.com/LumaPictures/gozbruh
    cd gozbruh
    python setup.py install
    ```

2.  Create a method for starting the Maya Command Port server either in 
    startup, or as a button on a shelf doing something like the following:

    ```python
    import gozbruh.maya_tools as maya_tools
    maya_tools.start_maya_server()
    ```

3.  Create a shelf button for sending information to zbrush.

    You can use the GUI:

    ```python
    import gozbruh.mayagui as mayagui
    sendWin = mayagui.Win()
    ```

    Or send the current selection with previously saved options:

    ```python
    import gozbruh.maya_tools as maya_tools
    maya_tools.send()
    ```


## Other Options

You have the option to add executable scripts which are run prior to starting up the tool.
The are available for either application in the configuration directory:

*  The default configuration directory is ~/.zbrush/gozbruh/
*  The default ZBrush pre-execution script is ~/.zbrush/gozbruh/ZBrushPreExec
*  The default Maya pre-execution script is ~/.zbrush/gozbruh/MayaPreExec

## Troubleshooting

As long as the setup occured correctly and the configuration directory and DefaultZScript.txt is present for ZBrush and the configuration directory is present for the Maya machine everything should work properly.

* If you see a  .gozbruhLog file in your home directory, you are missing either the config directory,   
  or the DefaultZScript directory.
* If you see a message about incorrect paths in ZBrush, check configuration files
* If you see a message about connectivity issues, or experience connectivity issues in either application, check your configuration files.
