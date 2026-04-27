# 1. BASE IMAGE: Start with a Python image suitable for data science (slim for smaller size)
FROM python:3.10-slim

# 2. ENVIRONMENT VARIABLES: Set the working directory inside the container
WORKDIR /app

# 3. COPY DEPENDENCIES: Copy the requirements file into the container
COPY requirements.txt .

# 4. INSTALL DEPENDENCIES: Install all Python packages
# The '--no-cache-dir' keeps the container small
RUN pip install --no-cache-dir -r requirements.txt

# 5. COPY APPLICATION CODE: Copy all local project files into the container
# NOTE: Ensure your .gitignore is up to date to exclude private keys and junk!
COPY . .

# 6. EXPOSE PORT: Inform Docker that the container runs on port 5000 (Flask default)
EXPOSE 5000

# 7. COMMAND TO RUN: Define the command that starts your Flask application
# We use Gunicorn, a production-grade WSGI server, to run your app_min.py
# If Gunicorn is not in requirements.txt, you may need to add it, 
# but for now, we'll assume a basic Flask run command works:
# CMD ["python", "app_min.py"]

# Alternative using Gunicorn (Recommended for production, requires Gunicorn in requirements.txt)
# Add 'gunicorn>=21.2.0' to your requirements.txt if using this:
# CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app_min:app"]

# Sticking with the Flask development server command for now:
CMD ["python3", "app_min.py"]
