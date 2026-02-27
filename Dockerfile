FROM python:3.9-slim
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir streamlit requests -i https://pypi.tuna.tsinghua.edu.cn/simple
EXPOSE 8501
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]