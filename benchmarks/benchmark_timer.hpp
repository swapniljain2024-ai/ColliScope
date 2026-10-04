#pragma once

#include <cstdint>

#ifdef _WIN32
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <windows.h>
#else
#include <chrono>
#endif

namespace colliscope {

/**
 * HighPrecisionTimer: Monotonic, sub-microsecond timer implementation.
 * 
 * On Windows: Uses QueryPerformanceCounter (QPC) and QueryPerformanceFrequency.
 * On x86_64 Windows systems, QPC typically runs at 10 MHz (100 ns resolution),
 * strictly monotonic, and immune to system time changes or NTP synchronization.
 * 
 * On POSIX: Uses std::chrono::steady_clock (typically clock_gettime CLOCK_MONOTONIC, 1 ns).
 */
class HighPrecisionTimer {
public:
    static inline uint64_t nowTicks() {
#ifdef _WIN32
        LARGE_INTEGER t;
        QueryPerformanceCounter(&t);
        return static_cast<uint64_t>(t.QuadPart);
#else
        return static_cast<uint64_t>(std::chrono::steady_clock::now().time_since_epoch().count());
#endif
    }

    static inline double getFrequency() {
#ifdef _WIN32
        LARGE_INTEGER f;
        QueryPerformanceFrequency(&f);
        return static_cast<double>(f.QuadPart);
#else
        return 1e9;
#endif
    }

    static inline double ticksToNanoseconds(uint64_t ticks) {
#ifdef _WIN32
        static const double freq = getFrequency();
        return (static_cast<double>(ticks) * 1e9) / freq;
#else
        return static_cast<double>(ticks);
#endif
    }

    static inline double ticksToSeconds(uint64_t ticks) {
#ifdef _WIN32
        static const double freq = getFrequency();
        return static_cast<double>(ticks) / freq;
#else
        return static_cast<double>(ticks) / 1e9;
#endif
    }

    /**
     * Empirically measures the minimum observable non-zero tick delta
     * between consecutive reads of the hardware timer.
     */
    static double measureEmpiricalResolutionNs() {
        uint64_t min_diff = UINT64_MAX;
        for (int i = 0; i < 2000; ++i) {
            uint64_t t1 = nowTicks();
            uint64_t t2 = nowTicks();
            while (t2 == t1) {
                t2 = nowTicks();
            }
            uint64_t diff = t2 - t1;
            if (diff < min_diff) {
                min_diff = diff;
            }
        }
        return ticksToNanoseconds(min_diff);
    }
};

} // namespace colliscope

