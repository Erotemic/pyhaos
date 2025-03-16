"""
Basic
"""
__version__ = '0.0.1'
__author__ = 'Jon Crall'
__author_email__ = 'erotemic@gmail.com'
__url__ = 'None'

__mkinit__ = """
mkinit /home/joncrall/code/pyhaos/pyhaos/__init__.py
"""
from pyhaos import websockets_api

from pyhaos.multi_api import (MultiAPI,)
from pyhaos.websockets_api import (AsyncWebSocketsAPI, WebSocketsAPI,)

__all__ = ['AsyncWebSocketsAPI', 'WebSocketsAPI', 'websockets_api', 'MultiAPI']
