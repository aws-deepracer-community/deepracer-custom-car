from rclpy.time import Time
from device_info_pkg import constants


class RingBuffer:
    """High-performance ring buffer for latency measurements."""

    def __init__(self, maxsize):
        self.maxsize = maxsize
        self.data = [(0.0, Time())] * maxsize  # Pre-allocate tuples (latency_ms, Time)
        self.index = 0
        self.size = 0

        # Running statistics for O(1) mean calculation
        self.running_sum = 0.0

    def append(self, latency_ms: float, timestamp: Time):
        """Add latency measurement - O(1) operation."""
        # If buffer is full, subtract the value being overwritten
        if self.size == self.maxsize:
            old_value, _ = self.data[self.index]
            self.running_sum -= old_value

        # Add new value
        self.data[self.index] = (latency_ms, timestamp)
        self.running_sum += latency_ms

        # Advance index
        self.index = (self.index + 1) % self.maxsize
        self.size = min(self.size + 1, self.maxsize)

    def get_mean(self):
        """Get mean in O(1) time."""
        return self.running_sum / self.size if self.size > 0 else 0.0

    def get_fps(self):
        """Calculate FPS using first and last timestamps - O(1)."""
        if self.size < 2:
            return 0.0

        if self.size < self.maxsize:
            # Buffer not full - simple case
            first_time = self.data[0][1]
            last_time = self.data[self.size - 1][1]
        else:
            # Buffer is full - handle wraparound
            first_time = self.data[self.index][1]  # Oldest entry
            last_index = (self.index - 1) % self.maxsize
            last_time = self.data[last_index][1]   # Newest entry

        time_diff_ns = (last_time - first_time).nanoseconds
        if time_diff_ns > 0:
            time_diff_s = time_diff_ns / 1_000_000_000.0
            return (self.size - 1) * constants.LATENCY_SAMPLE_RATE / time_diff_s
        return 0.0

    def get_percentile(self, percentile):
        """Get percentile (expensive operation - use sparingly)."""
        if self.size == 0:
            return 0.0

        # Extract values in correct order
        if self.size < self.maxsize:
            values = [self.data[i][0] for i in range(self.size)]
        else:
            # Handle wraparound
            values = []
            for i in range(self.size):
                idx = (self.index + i) % self.maxsize
                values.append(self.data[idx][0])

        values.sort()
        index = min(int(percentile * len(values)), len(values) - 1)
        if index < 0:
            index = 0
        return values[index]

    def clear(self):
        """Clear the buffer and reset statistics."""
        self.size = 0
        self.index = 0
        self.running_sum = 0.0

    def __len__(self):
        return self.size

    def __bool__(self):
        return self.size > 0
