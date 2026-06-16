FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade -r requirements.txt
COPY . .
RUN chmod +x /app/start.sh
EXPOSE 8080
CMD ["/app/start.sh"]
