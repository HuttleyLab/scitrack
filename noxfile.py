import nox


dependencies = "numpy", "click", "pytest", "pytest-cov"


@nox.session(python=[f"3.{v}" for v in range(7, 11)])
def test(session):
    session.install(*dependencies)
    session.install(".")
    session.chdir("tests")
    session.run(
        "pytest",
        "-x",
        "--cov-report",
        f"lcov:lcov-{session.python}.info",
        "--cov",
        "scitrack",
    )
