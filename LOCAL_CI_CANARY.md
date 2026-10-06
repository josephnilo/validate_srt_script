# Local CI pull-request canary

This temporary pull request verifies that Ubuntu Air tests
the current commit of an open pull request from this repository and reports its
result to that exact commit. Its deliberate failing test now verifies the live
CI warning and alert while another Air warning already exists. Remove only this
fixture in a new commit to verify recovery. Application code, dependencies and
the original CI recipe remain unchanged.

Close this canary without merging after the independent test and cleanup checks.

This additional temporary head was created while the local request timer was
deliberately paused, to verify that restarting it discovers missed work.
