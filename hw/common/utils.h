#ifndef __UTILS_H__
#define __UTILS_H__

constexpr int clog2(int n) {
    return (n <= 1) ? 0 : 1 + clog2((n + 1) / 2);
}

#endif
