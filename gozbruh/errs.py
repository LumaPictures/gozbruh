"""custom exceptions for go-zbruh"""

class GozbruhError(Exception):
    pass


class IpError(GozbruhError):
    """Exception raised for invalid IP addresses

    Attribitues
    -----------
    host : str
        input host address
    msg : str
        gui message

    """

    def __init__(self, host, msg):
        GozbruhError.__init__(self, msg)
        self.host = host
        self.msg = msg


class ZBrushServerError(GozbruhError):
    """Exception raised for connection failure

    Attribitues
    -----------
    msg : str
        gui message

    """


class PortError(GozbruhError):
    """Exception raised for invalid socket ports

    Attributes
    ----------
    port : str
        input port
    msg : str
        gui msg

    """

    def __init__(self, port, msg):
        GozbruhError.__init__(self, msg)
        self.port = port
        self.msg = msg
        self.message = msg


class SelectionError(GozbruhError):
    """Exception raise for no file mesh selected

    Attributes
    ----------
    msg : str
        gui msg

    """
