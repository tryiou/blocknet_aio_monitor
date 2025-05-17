import os
import subprocess
import sys
import time
import venv


class GitRepoManagement:
    def __init__(self, repo_url: str, target_dir: str, branch: str = "main"):
        self.repo_url = repo_url
        self.target_dir = os.path.abspath(target_dir)  # Always use absolute path
        self.branch = branch
        self.venv_dir = os.path.join(self.target_dir, "venv")

    def setup(self):
        """Main execution flow: clone/update repository and set up environment"""
        print(f"Working with repository: {self.repo_url}")
        print(f"Target directory: {os.path.abspath(self.target_dir)}")

        self.clone_or_update_repo()
        self.create_virtualenv()
        self.install_requirements()

        print(f"Repository setup complete: {self.repo_url} -> {os.path.abspath(self.target_dir)}")
        return True

    def run_script(self, script_path, script_args=None):
        """Execute a Python script using the virtual environment's Python interpreter"""
        if script_args is None:
            script_args = []

        # Ensure we're using absolute paths throughout
        abs_target_dir = os.path.abspath(self.target_dir)
        abs_script_path = os.path.abspath(os.path.join(abs_target_dir, script_path))
        if not os.path.isfile(abs_script_path):
            self._fail(f"Script not found: {abs_script_path}")

        cmd = [self._python_path(), abs_script_path] + script_args
        print(f"Running script: {' '.join(cmd)}")
        return self._run_command_with_output(cmd, cwd=self.target_dir)

    def clone_or_update_repo(self):
        target_dir = os.path.abspath(self.target_dir)
        git_dir = os.path.join(target_dir, ".git")
        
        if os.path.exists(target_dir):
            # Verify if it's actually a working git repository
            is_valid_repo = False
            if os.path.isdir(git_dir):
                try:
                    # Check git rev-parse to validate repository integrity
                    print(f"Validating git repository at '{target_dir}'...")
                    self._run_command(["git", "rev-parse", "--is-inside-work-tree"], cwd=target_dir)
                    is_valid_repo = True
                except subprocess.CalledProcessError:
                    print(f"Directory {target_dir} appears to be a corrupt git repo")
            
            if not is_valid_repo:
                print(f"Recreating invalid/missing git repository at {target_dir}")
                import shutil
                try:
                    # More thorough cleanup
                    if os.path.exists(target_dir):
                        shutil.rmtree(target_dir, ignore_errors=True)
                        # Double-check removal
                        for i in range(3):  # Try multiple times if needed
                            if not os.path.exists(target_dir):
                                break
                            time.sleep(0.1)
                            shutil.rmtree(target_dir, ignore_errors=True)
                except Exception as e:
                    self._fail(f"Failed to cleanup directory {target_dir}: {e}")
                
                # Create fresh directory
                os.makedirs(target_dir, exist_ok=True)
                print(f"Cloning fresh repository to {target_dir}")
                self._run_command(["git", "clone", "--branch", self.branch, self.repo_url, target_dir])
                return
                
            # If we got here, it's a valid repo - update it
            try:
                print(f"Updating existing repository at '{target_dir}'")
                self._run_command(["git", "fetch", "--all"], cwd=target_dir)
                self._run_command(["git", "checkout", self.branch], cwd=target_dir)
                self._run_command(["git", "reset", "--hard", f"origin/{self.branch}"], cwd=target_dir)
                self._run_command(["git", "pull", "--ff-only"], cwd=target_dir)
            except subprocess.CalledProcessError as e:
                self._fail(f"Failed to update repository: {e}")
                
        else:
            print(f"Cloning new repository to {target_dir}")
            os.makedirs(target_dir, exist_ok=True)
            self._run_command(["git", "clone", "--branch", self.branch, self.repo_url, target_dir])

    def create_virtualenv(self):
        """Create virtual environment inside the target directory"""
        print(f"Creating virtual environment in target directory: {self.target_dir}")
        print(f"Full venv path: {os.path.abspath(self.venv_dir)}")
        
        if os.path.isdir(self.venv_dir):
            print(f"Virtual environment already exists at '{os.path.abspath(self.venv_dir)}'. Skipping creation.")
            return

        print(f"Creating virtual environment at '{self.venv_dir}'...")
        try:
            # Make sure directory exists for the target venv
            os.makedirs(os.path.dirname(self.venv_dir), exist_ok=True)

            # Use system=True to ensure we're using the system-site-packages
            # This helps when running from a PyInstaller binary which might have limited access
            venv.create(self.venv_dir, with_pip=True, system_site_packages=True)

            # Verify venv creation
            bin_dir = "Scripts" if sys.platform == "win32" else "bin"
            venv_bin_path = os.path.join(self.venv_dir, bin_dir)
            if not os.path.isdir(venv_bin_path):
                self._fail(f"Virtual environment bin directory not found at {venv_bin_path}")

            print(f"Virtual environment created at {self.venv_dir}")
            print(f"Bin directory: {venv_bin_path}")
            if os.path.exists(os.path.join(venv_bin_path, "pip")):
                print("Pip found in virtual environment")
            elif os.path.exists(os.path.join(venv_bin_path, "pip3")):
                print("Pip3 found in virtual environment")
            else:
                print("Warning: Pip not found in virtual environment")

        except Exception as e:
            self._fail(f"Failed to create virtual environment: {e}")

    def install_requirements(self):
        requirements_path = os.path.join(self.target_dir, "requirements.txt")
        requirements_path_abs = os.path.abspath(requirements_path)

        if not os.path.isfile(requirements_path_abs):
            print("No requirements.txt found. Skipping installation.")
            return

        print("Installing requirements from requirements.txt...")
        # Wait a moment for venv to fully initialize
        import time
        time.sleep(1)

        pip_path = self._pip_path()
        print(f"Using pip at: {pip_path}")

        # Check if pip exists (for regular paths, not for commands like "python -m pip")
        if " -m pip" not in pip_path and not os.path.isfile(pip_path):
            print(f"Warning: Pip not found at {pip_path}. Trying alternative approach.")

            # Try using the Python interpreter directly to run pip
            python_path = self._python_path()
            if os.path.isfile(python_path):
                print(f"Using Python at: {python_path} with -m pip")
                self._run_command(
                    [python_path, "-m", "pip", "install", "-r", requirements_path_abs],
                    "Failed to install requirements",
                    cwd=self.target_dir
                )
                return
            else:
                self._fail(f"Neither pip nor python found. Cannot install requirements.")

        # Use pip directly if it was found
        if " -m pip" in pip_path:
            # Handle the special case of "python -m pip" string
            python_cmd, _ = pip_path.split(" -m pip")
            self._run_command(
                [python_cmd, "-m", "pip", "install", "-r", requirements_path_abs],
                "Failed to install requirements",
                cwd=self.target_dir
            )
        else:
            # Regular pip command
            self._run_command(
                [pip_path, "install", "-r", requirements_path_abs],
                "Failed to install requirements",
                cwd=self.target_dir
            )

    def _pip_path(self) -> str:
        bin_dir = "Scripts" if sys.platform == "win32" else "bin"

        # Use absolute paths
        venv_dir_abs = os.path.abspath(self.venv_dir)

        # Try pip and pip3
        pip_path = os.path.join(venv_dir_abs, bin_dir, "pip")
        if os.path.isfile(pip_path):
            return pip_path

        pip3_path = os.path.join(venv_dir_abs, bin_dir, "pip3")
        if os.path.isfile(pip3_path):
            return pip3_path

        # If neither exists, try to use system pip as fallback
        system_pip = self._find_executable("pip") or self._find_executable("pip3")
        if system_pip:
            print(f"Warning: Using system pip at {system_pip} as fallback")
            return system_pip

        # Last resort - try python -m pip
        return f"{self._python_path()} -m pip"

    def _python_path(self) -> str:
        bin_dir = "Scripts" if sys.platform == "win32" else "bin"

        # Use absolute paths
        venv_dir_abs = os.path.abspath(self.venv_dir)

        # Try python and python3
        python_path = os.path.join(venv_dir_abs, bin_dir, "python")
        if os.path.isfile(python_path):
            return python_path

        python3_path = os.path.join(venv_dir_abs, bin_dir, "python3")
        if os.path.isfile(python3_path):
            return python3_path

        # If neither exists, use system python as fallback
        return sys.executable

    def _run_command(self, cmd_list, error_message=None, cwd=None):
        try:
            # Ensure all path strings are absolute paths but skip URLs
            for i, cmd in enumerate(cmd_list):
                if (isinstance(cmd, str) and 
                    os.path.sep in cmd and 
                    not os.path.isabs(cmd) and 
                    not cmd.startswith(("http://", "https://"))):
                    cmd_list[i] = os.path.abspath(cmd)

            # For PyInstaller compatibility, ensure we're using absolute paths for executables
            if isinstance(cmd_list[0], str):
                if cmd_list[0] in ["git", "pip", "pip3", "python", "python3"] and not os.path.isabs(cmd_list[0]):
                    # First try to find the executable in our venv
                    bin_dir = "Scripts" if sys.platform == "win32" else "bin"
                    venv_executable = os.path.join(self.venv_dir, bin_dir, cmd_list[0])
                    if os.path.isfile(venv_executable):
                        cmd_list[0] = venv_executable
                    else:
                        # Fall back to system PATH
                        executable = self._find_executable(cmd_list[0])
                        if executable:
                            cmd_list[0] = executable
                            
                    # Special handling for git commands with repository URLs
                    if cmd_list[0] == "git" and len(cmd_list) > 2 and "clone" in cmd_list:
                        # Don't modify repository URL arguments
                        for i in range(1, len(cmd_list)):
                            if cmd_list[i] in ["fetch", "pull", "clone"] and i+1 < len(cmd_list):
                                # Skip URL modification for the next argument
                                i += 1
                                break

            # Add debug logging for the actual command being executed
            print(f"Final command being executed: {cmd_list}")

            # Print command for debugging
            cmd_str = " ".join(str(c) for c in cmd_list)
            print(f"Executing: {cmd_str}")
            if cwd:
                cwd_abs = os.path.abspath(cwd) if not os.path.isabs(cwd) else cwd
                print(f"Working directory: {cwd_abs}")
                cwd = cwd_abs  # Use absolute path for cwd

            # For PyInstaller, we need to handle the frozen environment
            if getattr(sys, 'frozen', False):
                startupinfo = None
                if sys.platform == "win32":
                    # Hide console window on Windows
                    startupinfo = subprocess.STARTUPINFO()
                    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

                subprocess.run(cmd_list, check=True, cwd=cwd, startupinfo=startupinfo)
            else:
                subprocess.run(cmd_list, check=True, cwd=cwd)

        except subprocess.CalledProcessError as e:
            msg = error_message or "Command failed"
            self._fail(f"{msg}: {e}")
        except FileNotFoundError as e:
            print(f"Error: {e}")
            print(f"Command that failed: {' '.join(str(c) for c in cmd_list)}")
            if cwd:
                print(f"Working directory: {cwd}")

            # Try to provide helpful diagnostics
            if e.filename:
                print(f"File not found: {e.filename}")
                parent_dir = os.path.dirname(e.filename)
                if os.path.exists(parent_dir):
                    print(f"Parent directory exists: {parent_dir}")
                    print(f"Contents of parent directory:")
                    try:
                        for item in os.listdir(parent_dir):
                            print(f"  - {item}")
                    except Exception as list_err:
                        print(f"  Could not list directory contents: {list_err}")
                else:
                    print(f"Parent directory does not exist: {parent_dir}")

            self._fail(f"Command failed: File not found")

    def _run_command_with_output(self, cmd_list, error_message=None, cwd=None):
        """Run a command and return the output"""
        try:
            # Handle executable path similar to _run_command
            if cmd_list[0] in ["git", "pip", "python"] and not os.path.isabs(cmd_list[0]):
                executable = self._find_executable(cmd_list[0])
                if executable:
                    cmd_list[0] = executable

            # Setup for PyInstaller compatibility
            startupinfo = None
            if getattr(sys, 'frozen', False) and sys.platform == "win32":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            result = subprocess.run(
                cmd_list,
                check=True,
                cwd=cwd,
                startupinfo=startupinfo,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            return result.stdout

        except subprocess.CalledProcessError as e:
            msg = error_message or "Command failed"
            self._fail(f"{msg}: {e}")
            return None

    def _find_executable(self, name):
        """Find the path to an executable in the system PATH"""
        if sys.platform == "win32" and not name.endswith(".exe"):
            name = name + ".exe"

        for path in os.environ["PATH"].split(os.pathsep):
            executable = os.path.join(path, name)
            if os.path.isfile(executable) and os.access(executable, os.X_OK):
                return executable

        return None

    def _fail(self, message):
        print(message)
        sys.exit(1)


if __name__ == "__main__":
    # Example usage with optional branch override
    git_repo_url = "https://github.com/tryiou/xbridge_trading_bots"
    local_target_dir = "xbridge_trading_bots"
    local_branch = "main"  # or "dev", "test", etc.

    setup = GitRepoManagement(git_repo_url, local_target_dir, local_branch)
    setup.setup()

    # Example of running a script after setup
    # setup.run_script("main.py", ["--config", "config.json"])
    # Example of running a script after setup
    setup.run_script("gui_pingpong.py")
    #, ["--config", "config.json"])
