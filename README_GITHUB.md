# Build TyreTrack for Windows with GitHub Actions

This project includes a Windows x64 portable build workflow. Upload the **extracted project files** to the root of your GitHub repository; do not upload only this ZIP file. Keep the hidden `.github` folder and its `workflows/windows-portable.yml` file.

1. Create or open the TyreTrack repository on GitHub.
2. Upload the extracted project contents to the repository root and commit them to the default branch.
3. Open **Actions** and select **TyreTrack Windows Portable Build**.
4. Select **Run workflow**, choose the branch you just updated, then run it.
5. Wait for the workflow to finish successfully. Open its run and download **TyreTrack-Windows-x64-Portable** from Artifacts.

The workflow installs the pinned Windows dependencies, runs `python -u run_ci_tests.py`, builds the portable EXE with `BUILD_WINDOWS.py`, and uploads diagnostics if a step fails.

For a failed run, open the failed step's log. The **TyreTrack-Build-Diagnostics** artifact contains the test/build logs when GitHub was able to create them.

This ZIP is a complete source repository snapshot with models and the GitHub workflow. It is not itself the compiled Windows application. Keep the current working PC installation and its data folders until the new artifact has passed testing on the development PC.
