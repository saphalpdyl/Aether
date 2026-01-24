from typing import Tuple

def split_bytes_to_gigawords_octets(total_bytes: int) -> Tuple[int, int]:
    # The RADIUS protocol uses 32-bit counters for octets, so counters > 4.29 GB will reset to 0 without splitting
    if total_bytes < 0:
        total_bytes = 0

    gigawords = total_bytes >> 32
    remaining_octets = total_bytes & 0xFFFFFFFF

    return gigawords, remaining_octets
