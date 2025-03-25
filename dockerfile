# Use an official Python base image
FROM python:3.10

# Set the working directory inside the container
WORKDIR /app

# Copy the code from the repo to the container
COPY . /app

# Install dependencies if requirements.txt exists
RUN pip install --no-cache-dir -r requirements.txt || echo "No requirements.txt found, skipping."

# Set the default command (modify this if needed)
CMD ["python", "app.py"]
