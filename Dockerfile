# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir flask requests

# Create a volume for user data
VOLUME /app/users

# Make port 5000 available to the world outside this container
EXPOSE 5000

# Create a non-root user and switch to it
RUN adduser --disabled-password --gecos '' appuser
USER appuser

# Run app.py when the container launches
CMD ["python", "webui.py"]
