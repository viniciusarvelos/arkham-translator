FROM python:3.13-slim

# Set workdir
WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY source ./source
COPY glossary ./glossary
COPY out ./out
COPY converter.py .
COPY translator.py .

# Run bash so you can choose script at runtime
CMD ["bash"]
