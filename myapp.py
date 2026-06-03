import vibedev

# Build a project from scratch (writes vibedev-output/ + project.json).
vibedev.run("create a pretty calculator app in python and flask")
#vibedev.run("Design a minimalistic Dog class in Python.")

# Then, in a later run, extend that same project with a new feature. Reads project.json
# to learn what's already there and rebuilds only the files the feature touches.
# test_scope="all" (default) tests the whole project; "changed" tests only new/modified files.
#vibedev.continue_development("add a square-root button", test_scope="changed")
