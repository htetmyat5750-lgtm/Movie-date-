from collections import deque
from dataclasses import dataclass
from typing import Optional


@dataclass
class Track:
    title: str
    stream: str          # local file path or URL
    requested_by: str
    is_video: bool = False
    duration: int = 0


class Queue:
    def __init__(self):
        self._q: dict[int, deque[Track]] = {}
        self._cur: dict[int, Optional[Track]] = {}

    def _init(self, cid: int):
        if cid not in self._q:
            self._q[cid] = deque()
            self._cur[cid] = None

    def current(self, cid: int) -> Optional[Track]:
        self._init(cid)
        return self._cur[cid]

    def set_current(self, cid: int, t: Optional[Track]):
        self._init(cid)
        self._cur[cid] = t

    def enqueue(self, cid: int, t: Track):
        self._init(cid)
        self._q[cid].append(t)

    def pop_next(self, cid: int) -> Optional[Track]:
        self._init(cid)
        if self._q[cid]:
            t = self._q[cid].popleft()
            self._cur[cid] = t
            return t
        self._cur[cid] = None
        return None

    def list(self, cid: int) -> list[Track]:
        self._init(cid)
        return list(self._q[cid])

    def clear(self, cid: int):
        self._init(cid)
        self._q[cid].clear()
        self._cur[cid] = None


Q = Queue()
