def test_deliberate_local_ci_failure_canary():
    raise AssertionError("Deliberate temporary CI failure; never merge this branch")
