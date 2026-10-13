# Hybrid Offline-First HMS

Documentation guide:
1. Read all the docs in [docs](docs/)
2. Prepare a module wise plan to build the project from scratch
3. Implement plan according to Spiral model.
4. Add unit tests with each few features
5. Ensure that setting up on any Operating system between Windows/Linux/MacOS is easy
6. Use containers and sandboxes to maximum effect (venv in python, docker for common build, etc.)
7. Optimise build/compile time and space.
8. Document stepwise progress and keep track of metrics mentioned in docs.
9. The entire environment should be offline centric for the initial prototype, but dependency injection should be done, so that connecting to cloud DB is easier (mostly supabase for testing purposes)