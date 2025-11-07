<<<<<<< HEAD
# filename: install_pytest_fix.ps1

# If 'pip' is not recognized, it's likely Python is not added to PATH in PowerShell.
# First, try using 'python -m pip' instead.

python -m pip install pytest

# If that still fails, check if Python is installed correctly:
# 1. Run 'python --version'
# 2. If 'python' is also not recognized, you need to reinstall Python and check the box "Add Python to PATH" during installation.

# Alternatively, you can manually add the Python Scripts path to your environment variables:
# Example paths (adjust if different on your system):
# C:\Users\mniv7\AppData\Local\Programs\Python\Python312\Scripts
# C:\Users\mniv7\AppData\Local\Programs\Python\Python312\

# Steps to fix PATH manually (if needed):
# 1. Press Win+S and search "Environment Variables"
# 2. Click "Edit the system environment variables"
# 3. In the System Properties window, click "Environment Variables"
# 4. Under "System Variables" or "User Variables", find "Path" and click Edit
# 5. Add both paths above if missing
# 6. Click OK and restart PowerShell
=======
# filename: install_pytest_fix.ps1

# If 'pip' is not recognized, it's likely Python is not added to PATH in PowerShell.
# First, try using 'python -m pip' instead.

python -m pip install pytest

# If that still fails, check if Python is installed correctly:
# 1. Run 'python --version'
# 2. If 'python' is also not recognized, you need to reinstall Python and check the box "Add Python to PATH" during installation.

# Alternatively, you can manually add the Python Scripts path to your environment variables:
# Example paths (adjust if different on your system):
# C:\Users\mniv7\AppData\Local\Programs\Python\Python312\Scripts
# C:\Users\mniv7\AppData\Local\Programs\Python\Python312\

# Steps to fix PATH manually (if needed):
# 1. Press Win+S and search "Environment Variables"
# 2. Click "Edit the system environment variables"
# 3. In the System Properties window, click "Environment Variables"
# 4. Under "System Variables" or "User Variables", find "Path" and click Edit
# 5. Add both paths above if missing
# 6. Click OK and restart PowerShell
>>>>>>> 0c0df91 (Initial push)
