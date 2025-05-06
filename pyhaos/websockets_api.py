"""
SeeAlso:
    https://github.com/designer-living/py-ha-ws-client/blob/main/py_ha_ws_client/client.py
    https://github.com/music-assistant/python-hass-client/blob/main/hass_client/client.py
    https://github.com/home-assistant/core/blob/dev/homeassistant/components/config/label_registry.py
"""
import json
import websockets
import ubelt as ub
import asyncio


class AsyncWebSocketsAPI:
    def __init__(self, websocket_url, token):
        self.token = token
        self.websocket_url = websocket_url
        self.connection = None
        self._next_id = 1
        self.response_futures = {}
        self.response_queue = asyncio.Queue()

    def _get_next_id(self):
        new_id = self._next_id
        self._next_id += 1
        return new_id

    async def connect(self):
        """Establish a WebSocket connection and authenticate."""
        self._next_id = 1
        self.connection = await websockets.connect(self.websocket_url)
        auth_message = await self.connection.recv()  # Receive 'auth_required'
        print(f'auth_message = {ub.urepr(auth_message, nl=1)}')

        await self.connection.send(json.dumps({"type": "auth", "access_token": self.token}))
        auth_response = await self.connection.recv()  # Receive 'auth_ok'

        auth_data = json.loads(auth_response)
        if auth_data.get("type") == "auth_ok":
            print("Authentication successful")
        else:
            raise Exception("Authentication failed")

        # Start a background task to process responses
        self.listener = asyncio.create_task(self._listen_for_responses())

    async def _listen_for_responses(self):
        """Continuously listen for responses and distribute them."""
        while True:
            try:
                response = await self.connection.recv()
            except Exception as ex:
                print('listener stopped')
                for f in self.response_futures.values():
                    f.set_exception(ex)
                break
            data = json.loads(response)
            message_id = data.get("id")

            if message_id in self.response_futures:
                self.response_futures[message_id].set_result(data)
                del self.response_futures[message_id]
            else:
                await self.response_queue.put(data)  # Store unexpected messages

    async def send_command(self, message):
        """Send a WebSocket command and return the response."""
        if self.connection is None:
            await self.connect()

        # await self.connection.send(json.dumps(message))
        # response = await self.connection.recv()
        # return json.loads(response)

        message_id = message['id']

        future = asyncio.get_running_loop().create_future()
        self.response_futures[message_id] = future
        await self.connection.send(json.dumps(message))

        return await future  # Wait for the response handled by `_listen_for_responses`

    # GETTERS

    async def get_devices(self):
        """Retrieve all devices from Home Assistant."""
        response = await self.send_command({"id": self._get_next_id(), "type": "config/device_registry/list"})
        return response

    async def get_entities(self):
        # https://github.com/home-assistant/core/blob/f3b23afc92185abe7156c27c4ce2f3a54556d8df/homeassistant/components/config/entity_registry.py#L126
        response = await self.send_command({"id": self._get_next_id(), "type": "config/entity_registry/list"})
        return response

    async def get_labels(self):
        # References:
        # https://github.com/home-assistant/core/blob/dev/homeassistant/components/config/label_registry.py
        response = await self.send_command({"id": self._get_next_id(), "type": "config/label_registry/list"})
        return response

    async def get_areas(self):
        response = await self.send_command({"id": self._get_next_id(), "type": "config/area_registry/list"})
        return response

    async def get_configs(self):
        response = await self.send_command({"id": self._get_next_id(), "type": "config_entries/get"})
        return response

    async def get_services(self):
        response = await self.send_command({"id": self._get_next_id(), "type": "get_services"})
        return response

    async def get_automations(self):
        # Note: automations are types of entities
        response = await self.get_entities()
        new_result = []
        for entity in response['result']:
            domain = entity['entity_id'].rsplit('.')[0]
            if domain == 'automation':
                new_result.append(entity)
        response['result'] = new_result
        return response

    async def get_states(self):
        response = await self.send_command({"id": self._get_next_id(), "type": "get_states"})
        return response

    async def add_label(self, name, icon=None, color=None, description=None):
        return await self.send_command({
            "id": self._get_next_id(),
            "type": "config/label_registry/create",
            "name": name,
            'icon': icon,
            'color': color,
            'description': description
        })

    async def update_device(self, device_id, **data):
        allowed = {'area_id', 'labels', 'disabled_by', 'name_by_user'}
        unknown = set(data.keys()) - allowed
        if unknown:
            raise Exception(unknown)
        return await self.send_command({
            "id": self._get_next_id(),
            "type": "config/device_registry/update",
            'device_id': device_id,
            **data,
        })

    async def update_devices(self, devices):
        """
        Update multiple devices asynchronously.

        Args:
            devices (List[dict]): each passed to update_device
        """
        awaitables = [self.update_device(**device) for device in devices]
        return await asyncio.gather(*awaitables)

    async def get_area(self, area_id):
        area_response = await self.get_areas()
        found = None
        for area in area_response['result']:
            if area['area_id'] == area_id:
                assert found is None, 'multiple non-unique area ids'
                found = area
        assert found is not None, 'does not exist'
        return found

    async def update_area(self, area_id, **kwargs):
        """
        Updates the area properties, but cannot update the area id.
        """
        # Doesnt look like unspecified items are overwritten, which is nice.
        # found = await self.get_area(area_id)
        allowed_edit_keys = {
            'floor_id', 'icon', 'labels', 'name', 'picture', 'aliases'
        }
        # print(f'found = {ub.urepr(found, nl=1)}')
        unsupported = ub.udict(kwargs) - allowed_edit_keys
        if unsupported:
            # print(f'allowed = {ub.urepr(found, nl=1)}')
            raise Exception(f'Unsupported keys {unsupported}')

        data = {
            'area_id': area_id,
            **kwargs
        }
        return await self.send_command({
            "id": self._get_next_id(),
            "type": "config/area_registry/update",
            **data,
        })

    async def remove_label(self, label_id):
        return await self.send_command({"id": self._get_next_id(), "type": "config/device_registry/remove_label", "label_id": label_id})

    async def add_area(self, name):
        return await self.send_command({"id": self._get_next_id(), "type": "config/area_registry/create", "name": name})

    async def remove_area(self, area_id):
        return await self.send_command({"id": self._get_next_id(), "type": "config/area_registry/delete", "area_id": area_id})

    async def list_integrations(self):
        return await self.send_command({"id": self._get_next_id(), "type": "config/integration/list"})

    async def add_integration(self, domain):
        return await self.send_command({"id": self._get_next_id(), "type": "config/integration/setup", "domain": domain})

    async def remove_integration(self, entry_id):
        return await self.send_command({"id": self._get_next_id(), "type": "config/integration/delete", "entry_id": entry_id})

    async def call_service(self, domain, service, service_data=None):
        if service_data is None:
            service_data = {}
        return await self.send_command(
            {"id": self._get_next_id(), "type": "call_service", "domain": domain, "service": service, "service_data": service_data},
        )

    async def restart(self):
        # self.listener.cancel()
        # await self.call_service(domain="homeassistant", service="restart", service_data={})
        try:
            print('Sending restart command')
            await self.call_service(domain="homeassistant", service="restart", service_data={})
        except websockets.ConnectionClosedOK:
            print('Connection was closed, which is expected')
        else:
            print('warning: Connection did not close')
            await self.close()
            print('warning: manually closed connection')
        # TODO: can we figure out if the restart was actually respected.
        # await asyncio.sleep(3)
        print('Reconnecting')
        # Wait to reconnect
        while True:
            try:
                await self.connect()
            except ConnectionRefusedError:
                print('waiting for restart')
                await asyncio.sleep(1)
            else:
                print('reconnected')
                return

    async def reload_all_configs(self):
        """
        Reloads all YAML configuration that can be reloaded without restarting
        Home Assistant.

        Ignore:
            # Code to figure out what the service names are
            services = self.get_services()
            result = services['result']
            for domain, items in sorted(result.items()):
                print(f'domain={domain}')

            for domain, items in sorted(result.items()):
                service_names = sorted(items.keys())
                if 'reload' in service_names:
                    print(f'domain={domain}')
                    print(service_names)

            ha_services = result['homeassistant']
            for service_name, info in ha_services.items():
                print(service_name)
                print(ub.urepr(info))
        """
        return await self.call_service(
            domain="homeassistant",
            service="reload_all",
            service_data={}
        )

    async def reload_automations(self):
        """
        Reload all automation YAML configurations in Home Assistant.
        """
        return await self.call_service(
            domain="automation",
            service="reload",
            service_data={}
        )

    # async def reload_config(self):
    #     """
    #     Reloads a specific YAML config.

    #     Ignore:
    #         # Code to figure out what the service names are
    #         services = self.ws.get_services()
    #         result = services['result']
    #         ha_services = result['homeassistant']
    #         for service_name, info in ha_services.items():
    #             print(service_name)
    #             print(ub.urepr(info))
    #     """
    #     return await self.call_service(
    #         domain="homeassistant",
    #         service="reload_all",
    #         service_data={}
    #     )

    async def close(self):
        """Close the WebSocket connection."""
        if self.connection:
            await self.connection.close()


class WebSocketsAPI:
    """
    Synchronous wrapper around the AsyncWebSocketsAPI

    Example:
        >>> websocket_url = 'ws://localhost:8123/api/websocket'
        >>> token = 'abiglongsecrettoken'
        >>> self = WebSocketsAPI(websocket_url, token)
        >>> entities = self.get_entities()
        >>> print(ub.dict_hist([e['entity_category'] for e in entities['result']]))
        >>> print(ub.dict_hist([e['platform'] for e in entities['result']]))
    """
    def __init__(self, websocket_url, token):
        """
        Ignore:
            # For developers
            self = MySetup().build().ws
        """
        self.async_api = AsyncWebSocketsAPI(websocket_url=websocket_url, token=token)
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def _get_next_id(self):
        return self.async_api._get_next_id()

    def __getattr__(self, name):
        async_method = getattr(self.async_api, name, None)
        # print(f'async_method = {ub.urepr(async_method, nl=1)}')
        if callable(async_method):
            def wrapper(*args, **kwargs):
                result = self.loop.run_until_complete(async_method(*args, **kwargs))
                if isinstance(result, dict) and 'success' in result:
                    if not result['success']:
                        raise Exception(str(result))
                return result
            return wrapper
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")

    def __dir__(self):
        basic = super().__dir__()
        full = basic + dir(self.async_api)
        return full
