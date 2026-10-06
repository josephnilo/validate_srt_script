# Local CI pull-request canary

This temporary pull request verifies that Ubuntu Air tests
the current commit of an open pull request from this repository and reports its
result to that exact commit. Its deliberate failing test verified the live
CI warning and alert while another Air warning already existed. The fixture is
now removed in this new commit to verify automatic recovery. Application code,
dependencies and the original CI recipe remain unchanged.

Close this canary without merging after the independent test and cleanup checks.

This final temporary head checks local reporting after the old hosted workflow
was disabled and the Ubuntu Air status became required for merging to main.

This additional temporary head was created while the local request timer was
deliberately paused, to verify that restarting it discovers missed work.
