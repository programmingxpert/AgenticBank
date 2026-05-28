import asyncio
import inspect
from src.utils.logger import logger

class EventEmitter:
    def __init__(self):
        self._listeners = {}

    def on(self, event: str, listener):
        if event not in self._listeners:
            self._listeners[event] = []
        self._listeners[event].append(listener)
        return self

    def emit(self, event: str, *args, **kwargs):
        if event not in self._listeners:
            return
        
        for listener in self._listeners[event]:
            try:
                if asyncio.iscoroutinefunction(listener):
                    # Schedules async listener on the current running loop
                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(listener(*args, **kwargs))
                    except RuntimeError:
                        # No running loop, run synchronously
                        asyncio.run(listener(*args, **kwargs))
                else:
                    listener(*args, **kwargs)
            except Exception as e:
                logger.error(f"Event emitter error in listener for {event}: {str(e)}")
