from device_info_pkg import constants

class RingBuffer:
    """High-performance ring buffer for latency measurements."""

    def __init__(self, maxsize):
        self.maxsize = maxsize
        self.data = [(0.0, 0)] * maxsize  # Pre-allocate tuples (latency_ms, timestamp_ns)
        self.index = 0
        self.size = 0

        # Running statistics for O(1) mean calculation
        self.running_sum = 0.0
        self.running_min = float('inf')
        self.running_max = float('-inf')

    def append(self, latency_ns, timestamp_ns):
        """Add latency measurement - O(1) operation."""
        old_value = 0.0

        # If buffer is full, subtract the value being overwritten
        if self.size == self.maxsize:
            old_value = self.data[self.index][0]
            self.running_sum -= old_value

        # Add new value
        self.data[self.index] = (latency_ns, timestamp_ns)
        self.running_sum += latency_ns

        # Update min/max
        self.running_min = min(self.running_min, latency_ns)
        self.running_max = max(self.running_max, latency_ns)

        # Advance index
        self.index = (self.index + 1) % self.maxsize
        self.size = min(self.size + 1, self.maxsize)

    def get_mean(self):
        """Get mean in O(1) time."""
        return self.running_sum / (self.size * 1.0e6) if self.size > 0 else 0.0

    def get_min_max(self):
        """Get min/max - may need recalculation if buffer wrapped."""
        if self.size == 0:
            return 0.0, 0.0
        return self.running_min / 1.0e6, self.running_max / 1.0e6

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

        time_diff_ns = last_time - first_time
        if time_diff_ns > 0:
            time_diff_s = time_diff_ns / 1_000_000_000.0
            return (self.size * constants.LATENCY_SAMPLE_RATE - 1) / time_diff_s
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
        index = int(percentile * len(values))
        return values[min(index, len(values) - 1)] / 1.0e6

    def clear(self):
        """Clear the buffer and reset statistics."""
        self.size = 0
        self.index = 0
        self.running_sum = 0.0
        self.running_min = float('inf')
        self.running_max = float('-inf')

    def __len__(self):
        return self.size

    def __bool__(self):
        return self.size > 0
