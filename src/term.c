#include "cb.h"
#include <signal.h>
#include <stdio.h>
#include <sys/select.h>
#include <termios.h>
#include <unistd.h>

static struct termios saved;

void term_raw(int on) {
    if (on) {
        struct termios t;
        tcgetattr(0, &saved);
        t = saved;
        t.c_lflag &= ~(tcflag_t)(ICANON | ECHO);
        tcsetattr(0, TCSANOW, &t);
        fputs("\x1b[?1049h\x1b[?25l", stdout);
    } else {
        fputs("\x1b[?25h\x1b[?1049l", stdout);
        tcsetattr(0, TCSANOW, &saved);
    }
    fflush(stdout);
}

/* One key, or -1 on timeout. Arrows come back as 'A'..'D' + 1000. */
int term_key(int ms) {
    fd_set f;
    struct timeval tv = {ms / 1000, ms % 1000 * 1000};
    unsigned char c, s[2];
    FD_ZERO(&f);
    FD_SET(0, &f);
    if (select(1, &f, NULL, NULL, &tv) <= 0 || read(0, &c, 1) != 1) return -1;
    if (c != 27) return c;
    tv.tv_sec = 0; tv.tv_usec = 20000;
    FD_ZERO(&f);
    FD_SET(0, &f);
    if (select(1, &f, NULL, NULL, &tv) <= 0 || read(0, &s[0], 1) != 1) return 27;
    if (s[0] == '[' && read(0, &s[1], 1) == 1) return 1000 + s[1];
    return 27;
}
