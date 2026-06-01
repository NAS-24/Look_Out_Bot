# 1. Use a lightweight Python/Linux base image
FROM python:3.11-slim

# 2. Set the working directory inside the container
WORKDIR /app

# 3. Copy just the requirements file first (for caching)
COPY requirements.txt .

# 4. Install the Python libraries
RUN pip install --no-cache-dir -r requirements.txt

# 5. CRITICAL: Install Playwright's specific browser and Linux system dependencies
RUN playwright install --with-deps chromium

# 6. Copy all your code into the container
COPY . .

# 7. Make the bash script executable
RUN chmod +x start.sh

# 8. Tell Docker what to run when the container starts
CMD ["./start.sh"]