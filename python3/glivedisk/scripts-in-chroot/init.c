/*
 * login(1)
 *
 * This program is derived from 4.3 BSD software and is subject to the
 * copyright notice below.
 *
 * Copyright (C) 2011 Karel Zak <kzak@redhat.com>
 * Rewritten to PAM-only version.
 *
 * Michael Glad (glad@daimi.dk)
 * Computer Science Department, Aarhus University, Denmark
 * 1990-07-04
 *
 * Copyright (c) 1980, 1987, 1988 The Regents of the University of California.
 * All rights reserved.
 *
 * Redistribution and use in source and binary forms are permitted
 * provided that the above copyright notice and this paragraph are
 * duplicated in all such forms and that any documentation,
 * advertising materials, and other materials related to such
 * distribution and use acknowledge that the software was developed
 * by the University of California, Berkeley.  The name of the
 * University may not be used to endorse or promote products derived
 * from this software without specific prior written permission.
 * THIS SOFTWARE IS PROVIDED ``AS IS'' AND WITHOUT ANY EXPRESS OR
 * IMPLIED WARRANTIES, INCLUDING, WITHOUT LIMITATION, THE IMPLIED
 * WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE.
 */
#include <sys/param.h>
#include <stdio.h>
#include <ctype.h>
#include <unistd.h>
#include <getopt.h>
#include <memory.h>
#include <time.h>
#include <sys/stat.h>
#include <sys/time.h>
#include <sys/resource.h>
#include <sys/file.h>
#include <termios.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/wait.h>
#include <signal.h>
#include <errno.h>
#include <grp.h>
#include <pwd.h>
#include <utmpx.h>
#include <stdlib.h>
#include <sys/syslog.h>

#ifdef HAVE_LINUX_MAJOR_H
# include <linux/major.h>
#endif

#include <netdb.h>
#include <security/pam_appl.h>

#ifdef HAVE_SECURITY_PAM_MISC_H
# include <security/pam_misc.h>
#elif defined(HAVE_SECURITY_OPENPAM_H)
# include <security/openpam.h>
#endif

#include "c.h"
#include "pathnames.h"
#include "strutils.h"
#include "nls.h"
#include "env.h"
#include "xalloc.h"
#include "all-io.h"
#include "fileutils.h"
#include "timeutils.h"
#include "ttyutils.h"
#include "pwdutils.h"

#include "logindefs.h"

#define LOGIN_EXIT_TIMEOUT     5

static char **argv0;
static size_t argv_lth;

/*
 * Login control struct
 */
struct login_context {
    const char    *tty_path;      /* ttyname() return value */
    const char    *tty_name;      /* tty_path without /dev prefix */
    const char    *tty_number;    /* end of the tty_path */
    mode_t        tty_mode;       /* chmod() mode */

    const char    *username;        /* points to PAM, pwd or cmd_username */

    struct passwd *pwd;        /* user info */
    char          *pwdbuf;     /* pwd strings */

    pam_handle_t    *pamh;        /* PAM handler */
    struct pam_conv conv;         /* PAM conversation */

    pid_t        pid;
};

/*
 * This bounds the time given to login.  Not a define, so it can
 * be patched on machines where it's too small.
 */
static int child_pid = 0;
static volatile sig_atomic_t got_sig = 0;

/*
 * This handler can be used to inform a shell about signals to login. If you have
 * (root) permissions, you can kill all login children by one signal to the
 * login process.
 *
 * Also, a parent who is session leader is able (before setsid() in the child)
 * to inform the child when the controlling tty goes away (e.g. modem hangup).
 */
static void sig_handler(int signal)
{
    if (child_pid)
        kill(-child_pid, signal);
    else
        got_sig = 1;
    if (signal == SIGTERM)
        kill(-child_pid, SIGHUP);    /* because the shell often ignores SIGTERM */
}

/*
 * Let us delay all exit() calls when the user is not authenticated
 * or the session not fully initialized (loginpam_session()).
 */
static void __attribute__((__noreturn__)) sleepexit(int eval)
{
    sleep((unsigned int)getlogindefs_num("FAIL_DELAY", LOGIN_EXIT_TIMEOUT));
    exit(eval);
}

static void process_title_init(int argc, char **argv)
{
    int i;
    char **envp = environ;

    /*
     * Move the environment so we can reuse the memory.
     * (Code borrowed from sendmail.)
     * WARNING: ugly assumptions on memory layout here;
     *          if this ever causes problems, #undef DO_PS_FIDDLING
     */
    for (i = 0; envp[i] != NULL; i++)
        continue;

    environ = xmalloc(sizeof(char *) * (i + 1));

    for (i = 0; envp[i] != NULL; i++)
        environ[i] = xstrdup(envp[i]);
    environ[i] = NULL;

    if (i > 0)
        argv_lth = envp[i - 1] + strlen(envp[i - 1]) - argv[0];
    else
        argv_lth = argv[argc - 1] + strlen(argv[argc - 1]) - argv[0];
    if (argv_lth > 1)
        argv0 = argv;
}

static void process_title_update(const char *username)
{
    size_t i;
    const char prefix[] = "login -- ";
    char buf[sizeof(prefix) + LOGIN_NAME_MAX];

    if (!argv0)
        return;

    if (sizeof(buf) < (sizeof(prefix) + strlen(username) + 1))
        return;

    snprintf(buf, sizeof(buf), "%s%s", prefix, username);

    i = strlen(buf);
    if (i > argv_lth - 2) {
        i = argv_lth - 2;
        buf[i] = '\0';
    }
    memset(argv0[0], '\0', argv_lth);    /* clear the memory area */
    strcpy(argv0[0], buf);

    argv0[1] = NULL;
}

/*
 * Nice and simple code provided by Linus Torvalds 16-Feb-93.
 * Non-blocking stuff by Maciej W. Rozycki, macro@ds2.pg.gda.pl, 1999.
 *
 * He writes: "Login performs open() on a tty in a blocking mode.
 * In some cases it may make login wait in open() for carrier infinitely,
 * for example if the line is a simplistic case of a three-wire serial
 * connection. I believe login should open the line in non-blocking mode,
 * leaving the decision to make a connection to getty (where it actually
 * belongs)."
 */
static void open_tty(const char *tty)
{
    int i, fd, flags;

    fd = open(tty, O_RDWR | O_NONBLOCK);
    if (fd == -1) {
        syslog(LOG_ERR, _("FATAL: can't reopen tty: %m"));
        sleepexit(EXIT_FAILURE);
    }

    if (!isatty(fd)) {
        close(fd);
        syslog(LOG_ERR, _("FATAL: %s is not a terminal"), tty);
        sleepexit(EXIT_FAILURE);
    }

    flags = fcntl(fd, F_GETFL);
    flags &= ~O_NONBLOCK;
    fcntl(fd, F_SETFL, flags);

    for (i = 0; i < fd; i++)
        close(i);
    for (i = 0; i < 3; i++)
        if (fd != i)
            dup2(fd, i);
    if (fd >= 3)
        close(fd);
}

static inline void chown_err(const char *what, uid_t uid, gid_t gid)
{
    syslog(LOG_ERR, _("chown (%s, %u, %u) failed: %m"), what, uid, gid);
}

static inline void chmod_err(const char *what, mode_t mode)
{
    syslog(LOG_ERR, _("chmod (%s, %u) failed: %m"), what, mode);
}

static void chown_tty(struct login_context *cxt)
{
    const char *grname;
    uid_t uid = cxt->pwd->pw_uid;
    gid_t gid = cxt->pwd->pw_gid;

    grname = getlogindefs_str("TTYGROUP", TTYGRPNAME);
    if (grname && *grname) {
        struct group *gr = getgrnam(grname);
        if (gr)    /* group by name */
            gid = gr->gr_gid;
        else    /* group by ID */
            gid = (gid_t) getlogindefs_num("TTYGROUP", gid);
    }
    if (fchown(0, uid, gid))                /* tty */
        chown_err(cxt->tty_name, uid, gid);
    if (fchmod(0, cxt->tty_mode))
        chmod_err(cxt->tty_name, cxt->tty_mode);
}

/*
 * Reads the current terminal path and initializes cxt->tty_* variables.
 */
static void init_tty(struct login_context *cxt)
{
    struct stat st;
    struct termios tt, ttt;

    cxt->tty_mode = (mode_t) getlogindefs_num("TTYPERM", TTY_MODE);

    get_terminal_name(&cxt->tty_path, &cxt->tty_name, &cxt->tty_number);

    /*
     * In case login is suid it was possible to use a hardlink as stdin
     * and exploit races for a local root exploit. (Wojciech Purczynski).
     *
     * More precisely, the problem is  ttyn := ttyname(0); ...; chown(ttyn);
     * here ttyname() might return "/tmp/x", a hardlink to a pseudotty.
     * All of this is a problem only when login is suid, which it isn't.
     */
    if (!cxt->tty_path || !*cxt->tty_path ||
        lstat(cxt->tty_path, &st) != 0 || !S_ISCHR(st.st_mode) ||
        (st.st_nlink > 1 && strncmp(cxt->tty_path, "/dev/", 5) != 0) ||
        access(cxt->tty_path, R_OK | W_OK) != 0) {

        syslog(LOG_ERR, _("FATAL: bad tty"));
        sleepexit(EXIT_FAILURE);
    }

    tcgetattr(0, &tt);
    ttt = tt;
    ttt.c_cflag &= ~HUPCL;

    if ((fchown(0, 0, 0) || fchmod(0, cxt->tty_mode)) && errno != EROFS) {

        syslog(LOG_ERR, _("FATAL: %s: change permissions failed: %m"),
                cxt->tty_path);
        sleepexit(EXIT_FAILURE);
    }

    /* Kill processes left on this tty */
    tcsetattr(0, TCSANOW, &ttt);

    /*
     * Let's close file descriptors before vhangup
     * https://lkml.org/lkml/2012/6/5/145
     */
    close(STDIN_FILENO);
    close(STDOUT_FILENO);
    close(STDERR_FILENO);

    signal(SIGHUP, SIG_IGN);    /* so vhangup() won't kill us */
    vhangup();
    signal(SIGHUP, SIG_DFL);

    /* open stdin,stdout,stderr to the tty */
    open_tty(cxt->tty_path);

    /* restore tty modes */
    tcsetattr(0, TCSAFLUSH, &tt);
}

static void loginpam_err(pam_handle_t *pamh, int retcode)
{
    const char *msg = pam_strerror(pamh, retcode);

    if (msg) {
        fprintf(stderr, "\n%s\n", msg);
    }
    pam_end(pamh, retcode);
    exit(EXIT_FAILURE);
}

static inline int is_pam_failure(int rc)
{
    return rc != PAM_SUCCESS;
}

static pam_handle_t *init_loginpam(struct login_context *cxt)
{
    pam_handle_t *pamh = NULL;
    int rc;

    rc = pam_start("login", cxt->username, &cxt->conv, &pamh);
    if (rc != PAM_SUCCESS) {
        fprintf(stderr, "Couldn't initialize PAM: %s", pam_strerror(pamh, rc));
        exit(EXIT_FAILURE);
    }

    if (cxt->tty_path) {
        rc = pam_set_item(pamh, PAM_TTY, cxt->tty_path);
        if (is_pam_failure(rc))
            loginpam_err(pamh, rc);
    }

    /* We don't need the original username. We have to follow PAM. */
    cxt->username = NULL;
    cxt->pamh = pamh;

    return pamh;
}

/*
 * Note that the position of the pam_setcred() call is discussable:
 *
 *  - the PAM docs recommend pam_setcred() before pam_open_session()
 *  - but the original RFC http://www.opengroup.org/rfc/mirror-rfc/rfc86.0.txt
 *    uses pam_setcred() after pam_open_session()
 *
 * The old login versions (before year 2011) followed the RFC. This is probably
 * not optimal, because there could be a dependence between some session modules
 * and the user's credentials.
 *
 * The best is probably to follow openssh and call pam_setcred() before and
 * after pam_open_session().                -- kzak@redhat.com (18-Nov-2011)
 *
 */
static void loginpam_session(struct login_context *cxt)
{
    int rc;
    pam_handle_t *pamh = cxt->pamh;

    rc = pam_setcred(pamh, PAM_ESTABLISH_CRED);
    if (is_pam_failure(rc))
        loginpam_err(pamh, rc);

    rc = pam_open_session(pamh, PAM_SILENT);
    if (is_pam_failure(rc)) {
        pam_setcred(cxt->pamh, PAM_DELETE_CRED);
        loginpam_err(pamh, rc);
    }

    rc = pam_setcred(pamh, PAM_REINITIALIZE_CRED);
    if (is_pam_failure(rc)) {
        pam_close_session(pamh, 0);
        loginpam_err(pamh, rc);
    }
}

/*
 * Detach the controlling terminal, fork, restore syslog stuff, and create
 * a new session.
 */
static void fork_session(struct login_context *cxt)
{
    struct sigaction sa, oldsa_hup, oldsa_term;

    signal(SIGALRM, SIG_DFL);
    signal(SIGQUIT, SIG_DFL);
    signal(SIGTSTP, SIG_IGN);

    memset(&sa, 0, sizeof(sa));
    sa.sa_handler = SIG_IGN;
    sigaction(SIGINT, &sa, NULL);

    sigaction(SIGHUP, &sa, &oldsa_hup);    /* ignore when TIOCNOTTY */

    /*
     * Detach the controlling tty.
     * We don't need the tty in a parent who only waits for a child.
     * The child calls setsid() that detaches from the tty as well.
     */
    ioctl(0, TIOCNOTTY, NULL);

    /*
     * We have to beware of SIGTERM, because leaving a PAM session
     * without pam_close_session() is a pretty bad thing.
     */
    sa.sa_handler = sig_handler;
    sigaction(SIGHUP, &sa, NULL);
    sigaction(SIGTERM, &sa, &oldsa_term);

    closelog();

    /*
     * We must fork before setuid(), because we need to call
     * pam_close_session() as root.
     */
    child_pid = fork();
    if (child_pid < 0) {
        warn(_("fork failed"));

        pam_setcred(cxt->pamh, PAM_DELETE_CRED);
        pam_end(cxt->pamh, pam_close_session(cxt->pamh, 0));
        sleepexit(EXIT_FAILURE);
    }

    if (child_pid) {
        /*
         * parent - wait for child to finish, then clean up session
         */
        close(STDIN_FILENO);
        close(STDOUT_FILENO);
        close(STDERR_FILENO);
        free_getlogindefs_data();

        sa.sa_handler = SIG_IGN;
        sigaction(SIGQUIT, &sa, NULL);
        sigaction(SIGINT, &sa, NULL);

        /* wait as long as any child is there */
        while (wait(NULL) == -1 && errno == EINTR) ;
        openlog("login", LOG_ODELAY, LOG_AUTHPRIV);

        pam_setcred(cxt->pamh, PAM_DELETE_CRED);
        pam_end(cxt->pamh, pam_close_session(cxt->pamh, 0));
        exit(EXIT_SUCCESS);
    }

    /*
     * child
     */
    sigaction(SIGHUP, &oldsa_hup, NULL);        /* restore old state */
    sigaction(SIGTERM, &oldsa_term, NULL);
    if (got_sig)
        exit(EXIT_FAILURE);

    /*
     * Problem: if the user's shell is a shell like ash that doesn't do
     * setsid() or setpgrp(), then a ctrl-\, sending SIGQUIT to every
     * process in the pgrp, will kill us.
     */

    /* start new session */
    setsid();

    /* make sure we have a controlling tty */
    open_tty(cxt->tty_path);
    openlog("login", LOG_ODELAY, LOG_AUTHPRIV);    /* reopen */

    /*
     * TIOCSCTTY: steal tty from other process group.
     */
    if (ioctl(0, TIOCSCTTY, 1))
        syslog(LOG_ERR, _("TIOCSCTTY failed: %m"));
    signal(SIGINT, SIG_DFL);
}

/*
 * Initialize $TERM, $HOME, ...
 */
static void init_environ(struct login_context *cxt)
{
    struct passwd *pwd = cxt->pwd;
    char *termenv, **env;
    char tmp[PATH_MAX];
    int len, i;

    termenv = getenv("TERM");
    if (termenv)
        termenv = xstrdup(termenv);

    /* destroy environment */
    environ = xcalloc(1, sizeof(char *));

    xsetenv("HOME", pwd->pw_dir, 0);    /* legal to override */
    xsetenv("USER", pwd->pw_name, 1);
    xsetenv("SHELL", pwd->pw_shell, 1);
    xsetenv("TERM", termenv ? termenv : "dumb", 1);
    free(termenv);

    if (pwd->pw_uid) {
        if (logindefs_setenv("PATH", "ENV_PATH", _PATH_DEFPATH) != 0)
            err(EXIT_FAILURE, _("failed to set the %s environment variable"), "PATH");

    } else if (logindefs_setenv("PATH", "ENV_ROOTPATH", NULL) != 0 &&
           logindefs_setenv("PATH", "ENV_SUPATH", _PATH_DEFPATH_ROOT) != 0) {
           err(EXIT_FAILURE, _("failed to set the %s environment variable"), "PATH");
    }

    /* mailx will give a funny error msg if you forget this one */
    len = snprintf(tmp, sizeof(tmp), "%s/%s", _PATH_MAILDIR, pwd->pw_name);
    if (len > 0 && (size_t)len < sizeof(tmp))
        xsetenv("MAIL", tmp, 0);

    /* LOGNAME is not documented in login(1) but HP-UX 6.5 does it. We'll
     * not allow modifying it.
     */
    xsetenv("LOGNAME", pwd->pw_name, 1);

    env = pam_getenvlist(cxt->pamh);
    for (i = 0; env && env[i]; i++)
        putenv(env[i]);
}

static void initialize(int argc, char **argv, struct login_context *cxt)
{
    int c;
    struct sigaction act;

    signal(SIGQUIT, SIG_IGN);
    signal(SIGINT, SIG_IGN);

    setpriority(PRIO_PROCESS, 0, 0);
    process_title_init(argc, argv);

    if (*argv) {
        char *p = *argv;

        /* username from command line */
        cxt->username = xstrdup(p);
    }
#ifdef HAVE_CLOSE_RANGE
    close_range(STDERR_FILENO + 1, ~0U);
#else
    ul_close_all_fds(STDERR_FILENO + 1, ~0U);
#endif
}

int main(int argc, char **argv)
{
    char *child_argv[10];
    int child_argc = 0;
    struct passwd *pwd;
    struct login_context cxt = {
        .tty_mode = TTY_MODE,          /* tty chmod() */
        .pid = getpid(),          /* PID */
#ifdef HAVE_SECURITY_PAM_MISC_H
        .conv = { misc_conv, NULL }      /* Linux-PAM conversation function */
#elif defined(HAVE_SECURITY_OPENPAM_H)
        .conv = { openpam_ttyconv, NULL } /* OpenPAM conversation function */
#endif
    };

    initialize(argc, argv, &cxt);

    setpgrp();     /* set pgid to pid this means that setsid() will fail */
    init_tty(&cxt);

    init_loginpam(&cxt);

    cxt.pwd = xgetpwnam(cxt.username, &cxt.pwdbuf);
    if (!cxt.pwd) {
        fprintf(stderr, "Invalid user name \"%s\". Abort.", cxt.username);
        pam_end(cxt.pamh, PAM_SYSTEM_ERR);
        exit(EXIT_FAILURE);
    }

    pwd = cxt.pwd;
    cxt.username = pwd->pw_name;

    /*
     * Initialize the supplementary group list. This should be done before
     * pam_setcred, because PAM modules might add groups during that call.
     *
     * Can cause problems if NIS, NIS+, LDAP or something similar is used
     * and the machine has network problems.
     */
    if (initgroups(pwd->pw_name, pwd->pw_gid) < 0) {
        fprintf(stderr, "groups initialization failed: %m");
        pam_end(cxt.pamh, PAM_SYSTEM_ERR);
        sleepexit(EXIT_FAILURE);
    }

    /*
     * Open PAM session (after successful authentication and account check).
     */
    loginpam_session(&cxt);

    endpwent();

    chown_tty(&cxt);

    if (setgid(pwd->pw_gid) < 0 && pwd->pw_gid) {
        fprintf(stderr, "setgid() failed");
        exit(EXIT_FAILURE);
    }

    if (pwd->pw_shell == NULL || *pwd->pw_shell == '\0')
        pwd->pw_shell = _PATH_BSHELL;

    init_environ(&cxt);        /* init $HOME, $TERM ... */

    process_title_update(pwd->username);

    /*
     * Detach the controlling terminal, fork, and create a new session
     * and reinitialize syslog stuff.
     */
    fork_session(&cxt);

    /* discard permissions last so we can't get killed and drop core */
    if (setuid(pwd->pw_uid) < 0 && pwd->pw_uid) {
        fprintf(stderr, "setuid() failed");
        exit(EXIT_FAILURE);
    }

    /* wait until here to change directory! */
    if (chdir(pwd->pw_dir) < 0) {
        fprintf(stderr, "%s: change directory failed", pwd->pw_dir);
        exit(EXIT_FAILURE);
    }

    /* if the shell field has a space: treat it like a shell script */
    if (strchr(pwd->pw_shell, ' ')) {
        char *buff;

        xasprintf(&buff, "exec %s", pwd->pw_shell);
        child_argv[child_argc++] = "/bin/sh";
        child_argv[child_argc++] = "-sh";
        child_argv[child_argc++] = "-c";
        child_argv[child_argc++] = buff;
    } else {
        char tbuf[PATH_MAX + 2], *p;

        tbuf[0] = '-';
        xstrncpy(tbuf + 1, ((p = strrchr(pwd->pw_shell, '/')) ?
                    p + 1 : pwd->pw_shell), sizeof(tbuf) - 1);

        child_argv[child_argc++] = pwd->pw_shell;
        child_argv[child_argc++] = xstrdup(tbuf);
    }

    child_argv[child_argc++] = NULL;

    execvp(child_argv[0], child_argv + 1);

    if (!strcmp(child_argv[0], "/bin/sh"))
        warn(_("couldn't exec shell script"));
    else
        warn(_("no shell"));

    exit(EXIT_SUCCESS);
}
