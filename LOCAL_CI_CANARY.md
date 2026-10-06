# Local CI pull-request canary

This temporary documentation-only pull request verifies that Ubuntu Air tests
the current commit of an open pull request from this repository and reports its
result to that exact commit. It does not change application code, dependencies,
tests, or the original CI recipe.

Close this canary without merging after the independent test and cleanup checks.

This additional temporary head was created while the local request timer was
deliberately paused, to verify that restarting it discovers missed work.
