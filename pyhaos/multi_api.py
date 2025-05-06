
class MultiAPI:
    """
    Enable access to home assistant via multiple different APIs, namely:

        * Websockets
        * REST
        * Direct SSH Access
    """

    def __init__(self, hostname, port, token, ssh_hostname=None):
        self.hostname = hostname
        self.port = port
        self.token = token
        self.ssh_hostname = ssh_hostname

        self._ws = None
        self._ssh = None
        self._rest = None

    @property
    def ws(self):
        """
        Return the web sockets interface
        """
        if self._ws is None:
            from pyhaos import WebSocketsAPI
            ws_url = f'ws://{self.hostname}:{self.port}/api/websocket'
            self._ws = WebSocketsAPI(ws_url, token=self.token)
        return self._ws

    @property
    def ssh(self):
        """
        Return the SSH filesystem interface
        """
        if self._ssh is None:
            from pyhaos.ssh_api import SSHAPI
            self._ssh = SSHAPI(self.ssh_hostname)
        return self._ssh

    @property
    def rest(self):
        """
        Return the REST interface
        """
        if self._rest is None:
            rest_url = f'http://{self.hostname}:{self.port}/api'
            from homeassistant_api import Client
            self._rest = Client(rest_url, self.token)
            self._rest.__enter__()
        return self._rest
