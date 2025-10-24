from typing import List, Any

class RingBuffer:
    def __init__(self, capacity: int):
        self.capacity = capacity
        self.data: List[Any] = []
        self.start = 0  # index of oldest
        self.size = 0

    def append(self, item: Any):
        if self.size < self.capacity:
            self.data.append(item)
            self.size += 1
        else:
            self.data[self.start] = item
            self.start = (self.start + 1) % self.capacity

    def __len__(self):
        return self.size

    def iter_from(self, idx: int):
        # yields items with logical indices >= idx (assuming sequential integers in 'seq')
        for i in range(self.size):
            pos = (self.start + i) % self.capacity
            yield self.data[pos]